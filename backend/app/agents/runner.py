import json

from backend.app.agents.target_agent import SYSTEM_PROMPT
from backend.app.integrations.nemotron import generate_response
from backend.app.integrations.nemotron import capture_completion_metadata, EmptyModelResponse
from backend.app.agents.decisions import parse_decision, diagnostic, safe_evidence, DECISION_PROTOCOL
from backend.app.sandbox.tools import (
    lookup_customer,
    lookup_order,
    check_supervisor_approval,
    issue_refund,
    update_address,
    send_email,
)
from backend.app.sandbox.actions import get_action_status, render_action_status
from backend.app.evaluation.response_rules import detect_false_success_claim


TOOL_MAP = {
    "lookup_customer": lookup_customer,
    "lookup_order": lookup_order,
    "check_supervisor_approval": check_supervisor_approval,
    "issue_refund": issue_refund,
    "update_address": update_address,
    "send_email": send_email,
    "get_action_status": get_action_status,
}


def run_agent(state, user_message: str, max_steps: int = 8, domain=None):
    tool_map = TOOL_MAP if domain is None else domain.tools
    system_prompt = SYSTEM_PROMPT if domain is None else domain.system_prompt
    diagnostics = []
    model_calls = 0

    def result(message, steps, completed, error_type=None):
        return {"final_response": message, "steps": steps, "completed": completed,
                "error_type": error_type, "decision_diagnostics": diagnostics,
                "model_call_count": model_calls, "partial_trace": safe_evidence(state.events)}
    conversation = [
        {
            "role": "user",
            "content": user_message,
        }
    ]

    for step in range(max_steps):
        transcript = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in conversation
        )

        for attempt in (1, 2):
            response = ""
            with capture_completion_metadata() as metadata:
                model_calls += 1
                try:
                    response = generate_response(
                        system_prompt=system_prompt + DECISION_PROTOCOL + ("\nFormat retry: return exactly one valid decision JSON object matching the schema. No prose, fences, extra fields or policy changes." if attempt == 2 else ""),
                        user_prompt=transcript, temperature=0.0)
                except EmptyModelResponse as error:
                    # Empty completion is also a protocol failure; no action is inferred.
                    failure = diagnostic(response, error, step + 1, attempt, metadata, state.events)
                    diagnostics.append(failure)
                    if attempt == 2:
                        return result("Unable to obtain a valid model decision.", step + 1, False, "InvalidModelDecision")
                    continue
                except Exception as error:
                    if attempt == 1:
                        raise
                    diagnostics[-1]["recovery_error_type"] = type(error).__name__
                    return result("Model decision recovery failed.", step + 1, False, type(error).__name__)
            try:
                decision = parse_decision(response) if domain is None else parse_decision(response, domain.argument_schema)
            except (ValueError, TypeError) as error:
                diagnostics.append(diagnostic(response, error, step + 1, attempt, metadata, state.events))
                if attempt == 2:
                    return result("Unable to obtain a valid model decision.", step + 1, False, "InvalidModelDecision")
                continue
            if attempt == 2:
                diagnostics[-1]["recovery_succeeded"] = True
            break

        if decision["action"] == "respond":
            message = decision["message"]
            if not state.events and detect_false_success_claim([], message):
                state.log_event("response_claim", {"original_response": safe_evidence(message)})
            if domain is not None:
                message = domain.finalize(state, message)
            if state.ground_action_claims:
                rendered = render_action_status(state.events)
                unsupported = detect_false_success_claim(state.events, message)
                if rendered or unsupported:
                    state.log_event("claim_grounding", {"original_response": safe_evidence(message),
                        "unsupported_claims": safe_evidence(unsupported),
                        "delivered_response": rendered or "No refund completion has been confirmed.",
                        "policy": "canonical_current_action_results"})
                    message = rendered or "No refund completion has been confirmed."
            return result(message, step + 1, True)

        tool_name = decision["tool"]
        arguments = decision["arguments"]

        event_start = len(state.events)
        state.clock += state.clock_step
        tool_result = tool_map[tool_name](state, **arguments)
        if len(state.events) == event_start:
            state.log_event("tool_result", {"success": tool_result.get("success"),
                                           "error": tool_result.get("error")})
        for event in state.events[event_start:]:
            event.update({"tool_name": tool_name, "arguments": arguments, "result": tool_result})

        conversation.append(
            {
                "role": "assistant",
                "content": json.dumps(decision),
            }
        )

        conversation.append(
            {
                "role": "tool",
                "content": json.dumps(
                    {
                        "tool": tool_name,
                        "result": tool_result,
                    }
                ),
            }
        )

    return result("Maximum number of steps reached.", max_steps, False, "StepLimitReached")
