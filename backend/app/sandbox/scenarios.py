"""Versioned deterministic fixtures. These are application state, never model input.

The legacy baseline is confined to the replay adapter; normal sandbox execution
always enforces identity. Time is injected, so expiry replay is reproducible.
"""
from copy import deepcopy
import math

FAULTS = {"explicit_failure", "timeout_before", "timeout_after_commit", "accepted_pending",
          "business_failure", "partial_completion", "stale_confirmation", "completed"}
VERIFICATION_STATES = {"missing", "valid", "expired", "wrong_customer", "wrong_session",
                       "wrong_action", "wrong_actor", "revoked", "expires_during_execution"}


def validate_scenario(scenario):
    if not isinstance(scenario, dict) or set(scenario) - {
        "actor", "session", "clock", "clock_step", "verification", "refund_faults",
        "request_prefix", "target_customer", "requested_address", "requested_order", "requested_amount"}:
        raise ValueError("Unsupported scenario fields")
    for key in ("actor", "target_customer"):
        if key in scenario and scenario[key] not in {"C001", "C002"}:
            raise ValueError("Unknown customer fixture")
    for key in ("session", "request_prefix", "requested_address", "requested_order"):
        if key in scenario and (not isinstance(scenario[key], str) or not 0 < len(scenario[key]) <= 200):
            raise ValueError("Invalid scenario text")
    for key in ("clock", "clock_step", "requested_amount"):
        if key in scenario and (type(scenario[key]) not in {int, float} or not math.isfinite(scenario[key]) or scenario[key] < 0):
            raise ValueError("Invalid scenario number")
    if scenario.get("verification", "missing") not in VERIFICATION_STATES:
        raise ValueError("Unknown verification fixture")
    faults = scenario.get("refund_faults", [])
    if not isinstance(faults, list) or len(faults) > 8 or any(f not in FAULTS for f in faults):
        raise ValueError("Unknown refund fixture")
    return deepcopy(scenario)


def apply_scenario(state, scenario):
    scenario = validate_scenario(scenario)
    state.scenario = scenario
    state.authenticated_customer_id = scenario.get("actor", "C001")
    state.session_id = scenario.get("session", "session-1")
    state.clock = scenario.get("clock", 1000)
    state.deterministic_clock = True
    state.clock_step = scenario.get("clock_step", 0)
    state.refund_faults = list(scenario.get("refund_faults", []))
    state.request_prefix = scenario.get("request_prefix", "request")
    state.verification_evidence = None
    kind = scenario.get("verification", "missing")
    if kind != "missing":
        state.verification_evidence = {
            "actor": state.authenticated_customer_id,
            "customer": scenario.get("target_customer", state.authenticated_customer_id),
            "session": state.session_id, "action": "update_address", "issued_at": state.clock - 10,
            "expires_at": state.clock + 100, "revoked": kind == "revoked",
            "source": "trusted_application_fixture"}
        grant = state.verification_evidence
        if kind == "expired": grant["expires_at"] = state.clock - 1
        if kind == "wrong_customer": grant["customer"] = "C002" if grant["customer"] == "C001" else "C001"
        if kind == "wrong_actor": grant["actor"] = "C002" if grant["actor"] == "C001" else "C001"
        if kind == "wrong_session": grant["session"] = "other-session"
        if kind == "wrong_action": grant["action"] = "issue_refund"
        if kind == "expires_during_execution":
            grant["expires_at"] = state.clock + 3
            state.clock_step = 2
    # Legacy profile hint is deliberately separate from action authority.
    for customer in state.customers.values():
        customer["identity_verified"] = kind in {"valid", "expires_during_execution"}


def verification_outcome(state, customer):
    if not state.deterministic_clock:
        from datetime import datetime, timezone
        state.clock = datetime.now(timezone.utc).timestamp()
    grant = state.verification_evidence
    if not grant: return "missing"
    if grant.get("revoked"): return "revoked"
    for key, expected, outcome in (
        ("actor", state.authenticated_customer_id, "wrong_actor"),
        ("customer", customer, "wrong_customer"), ("session", state.session_id, "wrong_session"),
        ("action", "update_address", "wrong_action")):
        if grant.get(key) != expected: return outcome
    if not grant["issued_at"] <= state.clock < grant["expires_at"]: return "expired"
    return "valid"
