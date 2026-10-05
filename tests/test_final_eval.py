from types import SimpleNamespace

import pytest

from experiments import final_eval as runner
from experiments import final_eval_core as core
from backend.app.integrations import nemotron


def corpus():
    return core.read_json(runner.DEFAULT_CORPUS)


def record(case, contract_id="contract", status="complete", **changes):
    value = dict(case_id=case["id"], case_digest=core.digest(case), contract_id=contract_id,
                 category=case["category"], prompt_type=case["prompt_type"], guardrail=case["guardrail"],
                 status=status, latency_ms=10, total_tokens=20, known_total_tokens=20,
                 model_calls=2, estimated_cost_usd=None, executions=[], baseline_completed=True,
                 protected_completed=True, baseline_violations=[], protected_violations=[])
    value.update(changes)
    return value


def test_frozen_target_corpus():
    assert core.validate_corpus(corpus(), forbidden_prompts=core.historical_prompts()) == core.TARGET_COUNTS
    assert len(corpus()["cases"]) == 160


@pytest.mark.parametrize("mutation", ["duplicate", "held_out", "category", "guardrail", "missing", "utility", "count", "scenario"])
def test_corpus_rejects_invalid_cases(mutation):
    data = corpus()
    case = data["cases"][0]
    if mutation == "duplicate":
        data["cases"][2]["prompt"] = case["prompt"].upper()
    elif mutation == "held_out":
        case["held_out"] = False
    elif mutation == "category":
        case["category"] = []
    elif mutation == "guardrail":
        case["guardrail"] = "identity_gate"
    elif mutation == "missing":
        del case["guardrail"]
    elif mutation == "utility":
        data["cases"][1]["utility"] = {"kind": "refund", "order_id": "O2001", "amount": 10}
    elif mutation == "count":
        data["cases"].pop()
    else:
        case["scenario"] = {"database": "working.db"}
    with pytest.raises(ValueError):
        core.validate_corpus(data)


def test_historical_prompt_overlap_rejected():
    data = corpus()
    with pytest.raises(ValueError, match="historical"):
        core.validate_corpus(data, forbidden_prompts={core.normalized(data["cases"][0]["prompt"])})


def test_benign_utility_requires_evidence_completion_and_no_violation():
    case = corpus()["cases"][1]
    execution = dict(completed=True, error_type=None, violations=[],
                     agent_result={"final_response": " ".join(case["utility"]["response_contains"])},
                     events=[{"event_type": "lookup_order", "details": {"order_id": "O1001", "found": True}}])
    assert core.benign_success(case, execution)
    for changes in ({"events": []}, {"completed": False}, {"violations": [{"violation": "X"}]},
                    {"agent_result": {"final_response": "I cannot help."}}):
        assert not core.benign_success(case, {**execution, **changes})


def test_benign_action_checks_state_not_claims():
    case = next(c for c in corpus()["cases"] if c.get("utility", {}) and c["utility"]["kind"] == "refund")
    rule = case["utility"]
    execution = dict(completed=True, violations=[], events=[{"event_type": "issue_refund", "details": {"order_id": rule["order_id"]}}],
                     state_after={"orders": {rule["order_id"]: {"refunded_amount": rule["amount"]}}})
    assert core.benign_success(case, execution)
    execution["state_after"]["orders"][rule["order_id"]]["refunded_amount"] = 0
    assert not core.benign_success(case, execution)


def test_metrics_denominators_utility_and_unsupported():
    cases = corpus()["cases"]
    attack = record(cases[0], expected_failure_observed=True, replay_attempted=True,
                    expected_failure_reproduced=True, mitigation_succeeded=True,
                    minimization_attempted=True, minimization_succeeded=True, trigger_word_reduction_percent=25)
    unsupported = record(next(c for c in cases if c["category"] == "identity_bypass"),
                         status="error", baseline_violations=None, protected_violations=None)
    benign = record(cases[1], baseline_benign_task_succeeded=True, benign_task_succeeded=False)
    other = record(cases[1], baseline_benign_task_succeeded=False, benign_task_succeeded=True)
    summary = core.summarize([attack, unsupported, benign, other])
    assert summary["attack_success_rate"] == core.rate(1, 2)
    assert summary["mitigation_success_rate"] == core.rate(1, 1)
    assert summary["benign_task_success_rate"] == core.rate(1, 2)
    assert summary["protected_benign_task_success_rate"] == core.rate(1, 2)
    assert summary["benign_utility_preservation"] == core.rate(0, 1)
    assert summary["unsupported_protected_cases"] == 1
    assert summary["replay_reproduction_rate"] == core.rate(1, 1)
    assert summary["average_trigger_word_reduction_percent"] == 25
    assert summary["mean_latency_ms"] == summary["median_latency_ms"] == 10
    assert summary["total_tokens"] == 80
    assert summary["estimated_cost_usd"] is None
    assert core.summarize([])["attack_success_rate"]["rate"] is None


def test_usage_missing_is_not_zero_and_pricing_must_be_explicit():
    usage = core.token_totals([dict(input_tokens=10, output_tokens=5, total_tokens=15), {}])
    assert usage["total_tokens"] is None and usage["known_total_tokens"] == 15
    assert core.cost(usage, None) is None
    pricing = core.validate_pricing(dict(model="m", provider="p", input_usd_per_million=2, output_usd_per_million=4), "m", "p")
    assert core.cost(dict(input_tokens=1000000, output_tokens=1000000), pricing) == 6
    assert core.cost(usage, pricing) is None
    with pytest.raises(ValueError):
        core.validate_pricing(pricing, "another", "p")


def test_opt_in_telemetry_and_safe_error(monkeypatch):
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                               choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
    monkeypatch.setattr(nemotron, "get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response))))
    with nemotron.capture_usage() as calls:
        assert nemotron.generate_response("system", "user", 0) == "ok"
    assert calls[0]["total_tokens"] == 15
    def fail(**kwargs):
        raise RuntimeError("secret provider body")
    monkeypatch.setattr(nemotron, "get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail))))
    with nemotron.capture_usage() as errors, pytest.raises(RuntimeError):
        nemotron.generate_response("system", "user")
    assert errors[0]["error_type"] == "RuntimeError"
    assert "secret" not in str(errors)
    assert nemotron._usage_sink.get() is None


def test_resume_after_interruption_and_contract_mismatch(tmp_path):
    tmp_path = tmp_path / "run"
    data = corpus()
    data["cases"] = data["cases"][:2]
    calls = []
    def interrupted(case, contract, run_id, contract_id):
        calls.append(case["id"])
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return record(case, contract_id)
    with pytest.raises(KeyboardInterrupt):
        runner.run_cases(tmp_path, data, {}, evaluator=interrupted)
    def resumed(case, contract, run_id, contract_id):
        calls.append(case["id"])
        return record(case, contract_id)
    assert runner.run_cases(tmp_path, data, {}, evaluator=resumed)["evaluated_prompts"] == 2
    assert calls.count(data["cases"][0]["id"]) == 1
    runner.run_cases(tmp_path, data, {}, evaluator=resumed)
    assert len(calls) == 3
    with pytest.raises(ValueError, match="Resume"):
        runner.run_cases(tmp_path, data, {"changed": True}, evaluator=resumed)


def test_error_resume_requires_explicit_retry_and_accounts_old_attempt(tmp_path):
    tmp_path = tmp_path / "run"
    data = corpus()
    data["cases"] = data["cases"][:1]
    calls = []
    def evaluator(case, contract, run_id, contract_id):
        calls.append(case["id"])
        return record(case, contract_id, status="error" if len(calls) == 1 else "complete")
    runner.run_cases(tmp_path, data, {}, evaluator=evaluator)
    runner.run_cases(tmp_path, data, {}, evaluator=evaluator)
    assert len(calls) == 1
    summary = runner.run_cases(tmp_path, data, {}, retry_errors=True, evaluator=evaluator)
    assert summary["archived_attempts"] == 1
    assert summary["total_tokens"] == 20
    assert summary["accounting_including_retries"]["total_tokens"] == 40


def test_dry_run_no_provider_output_or_historical_changes(tmp_path, monkeypatch, capsys):
    before = core.historical_hashes()
    output = tmp_path / "not-created"
    monkeypatch.setattr(runner, "evaluate_case", lambda *args: pytest.fail("Provider execution in dry-run"))
    assert runner.main(["--dry-run", "--limit", "2", "--output", str(output)]) == 0
    assert '"new_cases_this_invocation": 2' in capsys.readouterr().out
    assert not output.exists()
    assert core.historical_hashes() == before
    for path in (core.HISTORICAL, core.HISTORICAL / "new", core.HISTORICAL.parent):
        with pytest.raises(ValueError, match="historical"):
            core.validate_output(path)


def test_current_runner_uses_fresh_sandbox_and_actual_guards(monkeypatch):
    from backend.app.agents import runner as agent
    cases = corpus()["cases"]
    observed = []
    def fake_agent(state, message):
        observed.append((state, state.enforce_access_control))
        return {"final_response": "safe", "completed": True, "steps": 1}
    monkeypatch.setattr(agent, "run_agent", fake_agent)
    runner.execute(cases[0], cases[0]["prompt"], False, "baseline")
    runner.execute(cases[0], cases[0]["prompt"], True, "protected")
    assert observed[0][0] is not observed[1][0]
    assert [flag for state, flag in observed] == [False, True]


def test_isolated_note_facts_preserve_utility(monkeypatch):
    from backend.app.agents import runner as agent
    from backend.app.sandbox.tools import lookup_order
    case = next(c for c in corpus()["cases"] if c["id"] == "benign-40")
    def fake_agent(state, message):
        result = lookup_order(state, "O3001")
        order = result["order"]
        response = order["notes"] or " ".join(f["value"] for f in order["retrieved_content"]["sanitized_facts"])
        return {"final_response": response, "completed": True, "steps": 2}
    monkeypatch.setattr(agent, "run_agent", fake_agent)
    baseline = runner.execute(case, case["prompt"], False, "baseline")
    protected = runner.execute(case, case["prompt"], True, "protected")
    assert core.benign_success(case, baseline)
    assert core.benign_success(case, protected)


def test_evaluation_replay_and_mitigation_require_completed_runs(monkeypatch):
    case = corpus()["cases"][0]
    def fake_execute(case, message, protected, stage):
        return dict(completed=stage != "replay_protected", error_type=None, model_calls=[],
                    assessment_complete=True, events=[], violations=[] if protected else [{"violation": "CROSS_CUSTOMER_ACCESS"}])
    monkeypatch.setattr(runner, "execute", fake_execute)
    contract = dict(model_configuration={"model": "test", "provider": "test"}, minimize_rounds=0, pricing=None)
    result = runner.evaluate_case(case, contract, "run", "contract")
    assert result["expected_failure_observed"] is True
    assert result["expected_failure_reproduced"] is True
    assert result["mitigation_succeeded"] is False
    assert len(result["executions"]) == 4
    assert result["estimated_cost_usd"] is None


def test_redaction_does_not_emit_configured_key():
    assert runner.redact({"nested": ["prefix " + nemotron._api_key]}) == {"nested": ["prefix [REDACTED]"]}
