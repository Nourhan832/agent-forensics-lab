"""Strict decision protocol and bounded, secret-safe failure evidence."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
import math
import os
import re

_stage = ContextVar("decision_stage", default="agent_execution")


@contextmanager
def decision_stage(stage):
    token = _stage.set(stage)
    try:
        yield
    finally:
        _stage.reset(token)


def safe_evidence(value):
    """Redact before truncation; never put a partial credential in a preview."""
    from backend.app.integrations import nemotron
    secrets = {v for k, v in os.environ.items() if v and any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    if nemotron._api_key:
        secrets.add(nemotron._api_key)
    if isinstance(value, dict):
        return {k: safe_evidence(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_evidence(v) for v in value]
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
            value = value.replace(json.dumps(secret)[1:-1], "[REDACTED]")
        value = re.sub(r"(?i)\b(?:bearer\s+)[^\s\"']+", "Bearer [REDACTED]", value)
        value = re.sub(r"(?i)(?:api[_-]?key|password|secret|access[_-]?token)[\"']?\s*[:=]\s*[\"']?[^\s\"',}]+", "credential=[REDACTED]", value)
    return value


def strict_json(response):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Non-finite JSON number")
    return json.loads(response, object_pairs_hook=pairs, parse_constant=constant)


ARGUMENTS = {
    "get_action_status": {"request_id": "text"},
    "lookup_customer": {"customer_id": "customer"},
    "lookup_order": {"order_id": "order"},
    "check_supervisor_approval": {"order_id": "order"},
    "issue_refund": {"order_id": "order", "amount": "amount"},
    "update_address": {"customer_id": "customer", "new_address": "text"},
    "send_email": {"customer_id": "customer", "subject": "text", "body": "text"},
}

DECISION_PROTOCOL = """
Decision schema requirements: use exactly action/message for respond, or exactly action/tool/arguments for tool_call.
Every listed tool parameter is required; additional fields are forbidden. customer_id must be a C-prefixed numeric customer identifier, never an O-prefixed order identifier. order_id must be an O-prefixed numeric order identifier. Amounts must be finite positive numbers, never strings or booleans. Address, subject and body must be nonempty strings of at most 8000 characters. Choose the tool from the user's request and actual tool results; do not guess authorization or invent identifiers. JSON must have no duplicate fields, NaN or Infinity.
"""


def parse_decision(response, argument_schema=None):
    schema = ARGUMENTS if argument_schema is None else argument_schema
    decision = strict_json(response)
    if not isinstance(decision, dict):
        raise ValueError("Decision must be a JSON object")
    if decision.get("action") == "respond":
        if set(decision) != {"action", "message"} or not isinstance(decision["message"], str) or not decision["message"].strip():
            raise ValueError("Response requires exactly action and nonempty string message")
        return decision
    if decision.get("action") != "tool_call" or set(decision) != {"action", "tool", "arguments"}:
        raise ValueError("Decision requires a supported action and exact schema fields")
    tool, args = decision["tool"], decision["arguments"]
    if not isinstance(tool, str) or tool not in schema or not isinstance(args, dict) or set(args) != set(schema[tool]):
        raise ValueError("Tool and arguments must match the complete tool schema")
    for field, kind in schema[tool].items():
        value = args[field]
        if kind in {"amount", "units"}:
            try:
                valid = type(value) in ({int} if kind == "units" else {int, float}) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
        elif kind in {"customer", "order"}:
            valid = isinstance(value, str) and re.fullmatch(("C" if kind == "customer" else "O") + r"\d{1,20}", value) is not None
        else:
            valid = isinstance(value, str) and 0 < len(value.strip()) <= 8000
        if not valid:
            raise ValueError("Tool argument has an invalid type or value")
    return decision


def diagnostic(response, error, step, attempt, metadata, events):
    preview = safe_evidence(response)
    return {"stage": _stage.get(), "step": step, "attempt": attempt,
            "parser_error_type": type(error).__name__,
            "parser_message": safe_evidence(getattr(error, "msg", str(error)))[:500],
            "parser_offset": getattr(error, "pos", None), "parser_line": getattr(error, "lineno", None),
            "parser_column": getattr(error, "colno", None),
            **safe_evidence(metadata), "failed_response_preview": preview[:2000],
            "response_truncated": len(preview) > 2000,
            "partial_trace": safe_evidence(deepcopy(events)),
            "recovery_attempted": attempt == 1, "recovery_succeeded": False}
