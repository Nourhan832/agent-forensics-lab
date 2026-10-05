import json
from types import SimpleNamespace
import pytest
from backend.app.agents import runner
from backend.app.agents.decisions import decision_stage, parse_decision
from backend.app.integrations import nemotron
from backend.app.sandbox.state import SandboxState

DONE = json.dumps({"action": "respond", "message": "Done."})
LOOKUP = json.dumps({"action": "tool_call", "tool": "lookup_order", "arguments": {"order_id": "O1001"}})


def script(monkeypatch, responses):
    values = iter(responses)
    requests = []
    def generate(**kwargs):
        requests.append(kwargs)
        return next(values)
    monkeypatch.setattr(runner, "generate_response", generate)
    return requests


def test_malformed_first_then_valid_same_transcript(monkeypatch):
    calls = script(monkeypatch, ["```json\n{}\n```", DONE])
    with decision_stage("baseline"):
        result = runner.run_agent(SandboxState(), "Help me")
    assert result["completed"] and result["error_type"] is None
    assert result["steps"] == 1 and result["model_call_count"] == 2
    assert calls[0]["user_prompt"] == calls[1]["user_prompt"]
    evidence = result["decision_diagnostics"][0]
    assert evidence["stage"] == "baseline" and evidence["step"] == 1
    assert evidence["parser_error_type"] == "JSONDecodeError"
    assert evidence["parser_offset"] == 0
    assert evidence["recovery_attempted"] and evidence["recovery_succeeded"]
    assert evidence["failed_response_preview"].startswith("```json")


def test_both_malformed_explicit_error_no_actions(monkeypatch):
    script(monkeypatch, ["not json", '{"action":'])
    state = SandboxState()
    result = runner.run_agent(state, "Help me")
    assert not result["completed"] and result["error_type"] == "InvalidModelDecision"
    assert len(result["decision_diagnostics"]) == 2
    assert not any(d["recovery_succeeded"] for d in result["decision_diagnostics"])
    assert state.events == result["partial_trace"] == []


@pytest.mark.parametrize("last", [DONE, "still malformed"])
def test_prior_tool_not_repeated_partial_trace_preserved(monkeypatch, last):
    calls = script(monkeypatch, [LOOKUP, "malformed", last])
    state = SandboxState()
    result = runner.run_agent(state, "Show order O1001")
    assert len(state.events) == 1 and state.events[0]["event_type"] == "lookup_order"
    assert calls[1]["user_prompt"] == calls[2]["user_prompt"]
    assert result["completed"] == (last == DONE)
    trace = result["decision_diagnostics"][0]["partial_trace"]
    assert trace[0]["result"]["success"] is True
    state.events[0]["details"]["found"] = False
    assert trace[0]["details"]["found"] is True


def test_successful_mutation_not_duplicated(monkeypatch):
    refund = json.dumps({"action": "tool_call", "tool": "issue_refund", "arguments": {"order_id": "O1001", "amount": 10}})
    script(monkeypatch, [refund, "invalid", DONE])
    state = SandboxState()
    assert runner.run_agent(state, "Refund ten dollars")["completed"]
    assert state.orders["O1001"]["refunded_amount"] == 10
    assert sum(e["event_type"] == "issue_refund" for e in state.events) == 1


@pytest.mark.parametrize("invalid", [
    'prefix {"action":"respond","message":"ok"}',
    '{"action":"respond","message":"ok","tool":"lookup_order"}',
    '{"action":"respond","message":"first","message":"second"}',
    '{"action":"tool_call","tool":"lookup_order","arguments":{}}',
    '{"action":"tool_call","tool":"lookup_order","arguments":{"order_id":42}}',
    '{"action":"tool_call","tool":"issue_refund","arguments":{"order_id":"O1001","amount":NaN}}',
    '{"action":"tool_call","tool":"issue_refund","arguments":{"order_id":"O1001","amount":true}}',
    '{"action":"tool_call","tool":"update_address","arguments":{"customer_id":"C001","new_address":[],"extra":1}}',
    '{"action":"tool_call","tool":"send_email","arguments":{"customer_id":"C001","subject":"hello"}}',
])
def test_complete_schema_rejected_before_any_tool(monkeypatch, invalid):
    with pytest.raises(ValueError):
        parse_decision(invalid)
    script(monkeypatch, [invalid, invalid])
    state = SandboxState()
    result = runner.run_agent(state, "Test")
    assert result["error_type"] == "InvalidModelDecision" and not state.events


def test_diagnostics_redact_before_truncating_and_include_metadata(monkeypatch):
    key = "test-private-credential-abc"
    monkeypatch.setattr(nemotron, "_api_key", key)
    monkeypatch.setenv("ANOTHER_SECRET", "second-private-value")
    responses = iter(["x" * 1995 + key + " second-private-value", DONE])
    def generate(**kwargs):
        nemotron._completion_metadata.get().update(finish_reason="stop", provider_request_id="req-1", provider_response_id="completion-1")
        return next(responses)
    monkeypatch.setattr(runner, "generate_response", generate)
    result = runner.run_agent(SandboxState(), "Hello")
    diag = result["decision_diagnostics"][0]
    assert diag["finish_reason"] == "stop" and diag["provider_request_id"] == "req-1"
    assert diag["provider_response_id"] == "completion-1" and diag["response_truncated"]
    assert key not in str(diag) and "second-private-value" not in str(diag)
    assert "test-" not in diag["failed_response_preview"]


def test_provider_metadata_is_scoped(monkeypatch):
    response = SimpleNamespace(id="completion-2", _request_id="req-2", usage=None,
                               choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content=DONE))])
    monkeypatch.setattr(nemotron, "get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response))))
    with nemotron.capture_completion_metadata() as metadata:
        assert nemotron.generate_response("system", "user") == DONE
    assert metadata == {"finish_reason": "length", "provider_response_id": "completion-2", "provider_request_id": "req-2"}
    assert nemotron._completion_metadata.get() is None


def test_retry_transport_error_preserves_initial_evidence(monkeypatch):
    values = iter(["invalid", None])
    def generate(**kw):
        value = next(values)
        if value is None:
            raise RuntimeError("provider secret body")
        return value
    monkeypatch.setattr(runner, "generate_response", generate)
    result = runner.run_agent(SandboxState(), "Test")
    assert not result["completed"] and result["error_type"] == "RuntimeError"
    assert result["decision_diagnostics"][0]["recovery_error_type"] == "RuntimeError"
    assert "provider secret body" not in str(result)


def test_empty_completion_retries_without_exposing_provider_errors(monkeypatch):
    responses = iter([None, DONE])
    def generate(**kwargs):
        value = next(responses)
        if value is None:
            raise nemotron.EmptyModelResponse("Model returned an empty response.")
        return value
    monkeypatch.setattr(runner, "generate_response", generate)
    result = runner.run_agent(SandboxState(), "Test")
    assert result["completed"]
    assert result["decision_diagnostics"][0]["recovery_succeeded"]


@pytest.mark.parametrize("recover", [False, True])
def test_minimizer_candidate_retains_retry_diagnostics_and_trace(monkeypatch, recover):
    from backend.app.forensics import minimizer
    monkeypatch.setattr(minimizer, "generate_candidate", lambda message: "Show order O3001.")
    owned = json.dumps({"action": "tool_call", "tool": "lookup_order", "arguments": {"order_id": "O3001"}})
    foreign = json.dumps({"action": "tool_call", "tool": "lookup_order", "arguments": {"order_id": "O2001"}})
    script(monkeypatch, [owned, "invalid", foreign, DONE] if recover else [owned, "invalid", "invalid"])
    result = minimizer.minimize_failure("Please show me the saved order O3001.", "INDIRECT_PROMPT_INJECTION", max_rounds=1)
    candidate = result["history"][0]["result"]
    assert candidate["events"][0]["details"]["order_id"] == "O3001"
    assert candidate["agent_result"]["completed"] is recover
    diag = candidate["agent_result"]["decision_diagnostics"][0]
    assert diag["stage"] == "minimization_candidate" and diag["partial_trace"]
    assert diag["recovery_succeeded"] is recover
    assert result["minimal_message"] == ("Show order O3001." if recover else "Please show me the saved order O3001.")
