"""Final-code held-out evaluation. Dry runs never call a provider or write results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.final_eval_core import (
    ROOT, SCHEMA_VERSION, EXPECTED, GUARDS, atomic_json, benign_success, cost, digest,
    historical_hashes, historical_prompts, load_records, pending_cases, read_json, run_lock,
    summarize, token_totals, validate_corpus, validate_output, validate_pricing,
)

DEFAULT_CORPUS = ROOT / "experiments" / "corpora" / "final_v1.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hash():
    paths = sorted((ROOT / "backend").rglob("*.py")) + sorted((ROOT / "experiments").glob("final_eval*.py"))
    paths += [ROOT / "requirements-lock.txt"]
    return digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def git_commit():
    try:
        result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def safe_configuration():
    from backend.app.integrations import nemotron
    return {**nemotron.model_configuration(), "endpoint_host": urlparse(nemotron._base_url or "").hostname,
            "agent_temperature": 0.0, "minimizer_temperature": 0.0, "max_agent_steps": 8,
            "timeout_seconds": float(os.getenv("NEBIUS_TIMEOUT_SECONDS", "45")), "sdk_max_retries": 1,
            "max_decision_format_retries": 1, "decision_schema_version": "1",
            "content_extractor_version": "business-facts-1"}


def redact(value):
    from backend.app.integrations import nemotron
    secret = nemotron._api_key
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


def execute(case, message, protected, stage):
    from backend.app.agents.runner import run_agent
    from backend.app.evaluation.oracle import evaluate_run
    from backend.app.integrations.nemotron import capture_usage
    from backend.app.sandbox.state import SandboxState
    from backend.app.agents.decisions import decision_stage
    guardrail = case["guardrail"]
    state = SandboxState(enforce_access_control=protected and guardrail == "access_control",
                         isolate_untrusted_content=protected and guardrail == "content_isolation",
                         simulate_refund_failure=case["category"] == "false_action_claim")
    scenario = case.get("scenario", {})
    for order, notes in scenario.get("order_notes", {}).items():
        state.orders[order]["notes"] = notes
    for customer, verified in scenario.get("identity_verified", {}).items():
        state.customers[customer]["identity_verified"] = verified
    start, error_type, result = perf_counter(), None, None
    with capture_usage() as calls:
        try:
            with decision_stage(stage):
                result = run_agent(state, message)
            error_type = result.get("error_type")
        except Exception as error:
            error_type = type(error).__name__
    # Partial successful actions remain violations even if a later model call fails.
    violations = evaluate_run(state.events, result["final_response"] if result else "")
    return {"execution_id": str(uuid4()), "stage": stage, "protected": protected,
            "completed": bool(result and result.get("completed")), "error_type": error_type,
            "agent_result": result, "events": state.events, "violations": violations,
            "assessment_complete": bool(result and result.get("completed")),
            "state_after": {"orders": state.orders, "customers": state.customers},
            "latency_ms": round((perf_counter() - start) * 1000, 3),
            "model_calls": calls, "usage": token_totals(calls)}


def evaluate_case(case, contract, run_id, contract_id):
    from backend.app.integrations.nemotron import capture_usage
    from backend.app.forensics.minimizer import minimize_failure
    start = perf_counter()
    config = contract["model_configuration"]
    record = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "case_run_id": str(uuid4()),
              "case_id": case["id"], "case_digest": digest(case), "contract_id": contract_id,
              "timestamp": now(), "category": case["category"], "prompt": case["prompt"],
              "prompt_type": case["prompt_type"], "held_out": case["held_out"],
              "model": config["model"], "provider": config["provider"], "model_configuration": config,
              "guardrail": case["guardrail"], "expected_failure_class": case["expected_failure_class"],
              "baseline_completed": False, "protected_completed": None,
              "baseline_violations": None, "protected_violations": None,
              "expected_failure_observed": None, "expected_failure_reproduced": None,
              "replay_attempted": False, "mitigation_succeeded": None,
              "baseline_benign_task_succeeded": None, "benign_task_succeeded": None,
              "minimization_attempted": False, "minimization_succeeded": None,
              "minimization_result": None, "trigger_word_reduction_percent": None,
              "executions": [], "errors": [], "status": "complete",
              "protected_support": "implemented" if case["guardrail"] else "unsupported_in_current_implementation"}
    all_calls = []
    def run(message, protected, stage):
        execution = execute(case, message, protected, stage)
        record["executions"].append(execution)
        all_calls.extend(execution["model_calls"])
        if execution["error_type"]:
            record["errors"].append({"stage": stage, "error_type": execution["error_type"]})
        return execution
    baseline = run(case["prompt"], False, "baseline")
    record["baseline_completed"] = baseline["completed"]
    record["baseline_violations"] = baseline["violations"] if baseline["assessment_complete"] or baseline["events"] else None
    expected = case["expected_failure_class"]
    if expected:
        found = any(v["violation"] == expected for v in baseline["violations"])
        record["expected_failure_observed"] = True if found else (False if baseline["assessment_complete"] else None)
    protected = None
    if case["guardrail"]:
        protected = run(case["prompt"], True, "protected")
        record["protected_completed"] = protected["completed"]
        record["protected_violations"] = protected["violations"] if protected["assessment_complete"] or protected["events"] else None
    if case["prompt_type"] == "benign":
        record["baseline_benign_task_succeeded"] = benign_success(case, baseline)
        record["benign_task_succeeded"] = benign_success(case, protected)
    elif record["expected_failure_observed"] is True:
        trigger = case["prompt"]
        rounds = contract["minimize_rounds"]
        # The existing minimizer cannot preserve custom fixtures or failed-refund state.
        if rounds and case["category"] in GUARDS and not case.get("scenario"):
            record["minimization_attempted"] = True
            with capture_usage() as calls:
                try:
                    result = minimize_failure(trigger, expected, max_rounds=rounds)
                    record["minimization_result"] = result
                    trigger = result["minimal_message"]
                    record["trigger_word_reduction_percent"] = result["reduction_percent"]
                    record["minimization_succeeded"] = result["reduction_percent"] > 0 and any(
                        h.get("reproduced") and h.get("result", {}).get("agent_result", {}).get("completed")
                        for h in result["history"] if h.get("result"))
                except Exception as error:
                    record["minimization_succeeded"] = False
                    record["errors"].append({"stage": "minimization", "error_type": type(error).__name__})
            all_calls.extend(calls)
            record["minimization_model_calls"] = calls
            # Each minimizer round starts with one proposal, followed by steps of its candidate run.
            cursor = 0
            for history in (record["minimization_result"] or {}).get("history", []):
                cursor += 1
                candidate = history.get("result")
                if candidate:
                    steps = candidate["agent_result"].get("model_call_count", candidate["agent_result"]["steps"])
                    candidate_calls = calls[cursor:cursor + steps]
                    cursor += steps
                    record["executions"].append({"execution_id": str(uuid4()), "stage": "minimization_candidate",
                        "completed": candidate["agent_result"].get("completed", False), "agent_result": candidate["agent_result"],
                        "error_type": candidate["agent_result"].get("error_type"),
                        "events": candidate["events"], "violations": candidate["violations"],
                        "usage": token_totals(candidate_calls), "model_calls": candidate_calls,
                        "latency_ms": sum(c["latency_ms"] for c in candidate_calls), "latency_scope": "provider_calls_only"})
                    if candidate["agent_result"].get("error_type"):
                        record["errors"].append({"stage": "minimization_candidate", "error_type": candidate["agent_result"]["error_type"]})
        record["replay_attempted"] = True
        replay_baseline = run(trigger, False, "replay_baseline")
        reproduced = any(v["violation"] == expected for v in replay_baseline["violations"])
        record["expected_failure_reproduced"] = reproduced if replay_baseline["assessment_complete"] else (True if reproduced else None)
        if case["guardrail"]:
            replay_protected = run(trigger, True, "replay_protected")
            record["mitigation_succeeded"] = (reproduced and replay_baseline["completed"] and
                                               replay_protected["completed"] and not replay_protected["violations"])
    usage = token_totals(all_calls)
    record.update(usage)
    record["estimated_cost_usd"] = cost(usage, contract["pricing"]) if not record["errors"] else None
    record["latency_ms"] = round((perf_counter() - start) * 1000, 3)
    record["status"] = "error" if record["errors"] else "complete"
    return redact(record)


def run_cases(output, corpus, contract, limit=None, retry_errors=False, evaluator=evaluate_case):
    output = validate_output(output)
    output.mkdir(parents=True, exist_ok=True)
    contract_id = digest(contract)
    with run_lock(output):
        metadata_path = output / "metadata.json"
        if metadata_path.exists():
            metadata = read_json(metadata_path)
            if metadata["contract_id"] != contract_id or metadata["contract"] != contract:
                raise ValueError("Resume requires unchanged corpus, source, Python, model/configuration and pricing")
        else:
            if any(output.iterdir()) and any(p.name != ".runner.lock" for p in output.iterdir()):
                raise ValueError("New benchmark output directory must be empty")
            metadata = {"schema_version": SCHEMA_VERSION, "run_id": str(uuid4()), "timestamp": now(),
                        "git_commit": git_commit(), "contract_id": contract_id, "contract": contract,
                        "planned_prompts": len(corpus["cases"]), "evaluated_prompts": 0}
            atomic_json(metadata_path, metadata)
        (output / "records").mkdir(exist_ok=True)
        records = load_records(output, corpus["cases"], contract_id)
        pending = pending_cases(corpus["cases"], records, limit, retry_errors)
        try:
            for case in pending:
                # An interrupted in-flight case may repeat; finalized cases never repeat by default.
                record = evaluator(case, contract, metadata["run_id"], contract_id)
                path = output / "records" / (case["id"] + ".json")
                if path.exists():
                    (output / "attempts").mkdir(exist_ok=True)
                    atomic_json(output / "attempts" / (case["id"] + "-" + str(uuid4()) + ".json"), read_json(path))
                atomic_json(path, record)
                print(f"{case['id']}: {record['status']}", flush=True)
        finally:
            records = load_records(output, corpus["cases"], contract_id)
            summary = summarize(records)
            archived = [read_json(p) for p in sorted((output / "attempts").glob("*.json"))]
            # Quality rates describe latest records; expenditure includes previous paid attempts.
            accounting = summarize(records + archived)
            summary["accounting_including_retries"] = {key: accounting[key] for key in (
                "total_tokens", "known_total_tokens", "model_calls", "estimated_cost_usd", "agent_executions")}
            summary["archived_attempts"] = len(archived)
            summary["by_category"] = {category: summarize([r for r in records if r["category"] == category])
                                      for category in sorted({r["category"] for r in records})}
            summary["benign_by_guardrail"] = {guard: summarize([r for r in records if r["prompt_type"] == "benign" and r["guardrail"] == guard])
                                             for guard in sorted(set(GUARDS.values()))}
            metadata.update({"updated_at": now(), "evaluated_prompts": len(records),
                             "remaining_prompts": len(corpus["cases"]) - len(records)})
            atomic_json(output / "summary.json", summary)
            atomic_json(metadata_path, metadata)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="Maximum new/retried case records this invocation, not provider calls")
    parser.add_argument("--minimize-rounds", type=int, default=1, help="0 disables minimization; maximum 5")
    parser.add_argument("--pricing-json", type=Path)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--allow-non-target-corpus", action="store_true")
    args = parser.parse_args(argv)
    before = historical_hashes()
    try:
        if args.limit is not None and args.limit < 1 or not 0 <= args.minimize_rounds <= 5:
            raise ValueError("Limit must be positive; minimization rounds must be 0 through 5")
        corpus = read_json(args.corpus)
        counts = validate_corpus(corpus, not args.allow_non_target_corpus, historical_prompts())
        config = safe_configuration()
        from backend.app.integrations import nemotron
        if nemotron._api_key and nemotron._api_key in json.dumps(corpus):
            raise ValueError("Corpus contains configured credential material")
        pricing = validate_pricing(read_json(args.pricing_json) if args.pricing_json else None, config["model"], config["provider"])
        contract = {"schema_version": SCHEMA_VERSION, "corpus_id": corpus["corpus_id"], "corpus_digest": digest(corpus),
                    "source_digest": source_hash(), "python_version": platform.python_version(),
                    "model_configuration": config, "minimize_rounds": args.minimize_rounds, "pricing": pricing,
                    "historical_artifacts_sha256": before}
        output = validate_output(args.output) if args.output else ROOT / "experiments" / "runs" / ("final-" + str(uuid4()))
        records = []
        if (output / "metadata.json").exists():
            if read_json(output / "metadata.json")["contract_id"] != digest(contract):
                raise ValueError("Existing output has a different benchmark contract")
            records = load_records(output, corpus["cases"], digest(contract))
        pending = pending_cases(corpus["cases"], records, args.limit, args.retry_errors)
        if args.dry_run:
            print(json.dumps({"dry_run": True, "schema_version": SCHEMA_VERSION, "corpus_digest": digest(corpus),
                              "planned_prompts": len(corpus["cases"]), "counts": counts, "previously_recorded": len(records),
                              "new_cases_this_invocation": len(pending), "provider_calls": 0,
                              "protected_comparison_supported": list(GUARDS), "model_configured": config["configured"],
                              "pricing_configured": pricing is not None}, indent=2))
            return 0
        if not config["configured"]:
            raise ValueError("Provider configuration is incomplete; dry-run is available without credentials")
        summary = run_cases(output, corpus, contract, args.limit, args.retry_errors)
        print(json.dumps({"output": str(output), "evaluated_prompts": summary["evaluated_prompts"],
                          "errors": summary["error_cases"], "total_tokens": summary["total_tokens"],
                          "estimated_cost_usd": summary["estimated_cost_usd"]}))
        return 1 if summary["error_cases"] else 0
    except (ValueError, OSError, KeyError) as error:
        # Validation messages contain field names, not prompts, provider bodies or credentials.
        print("Benchmark could not proceed:", str(error) if isinstance(error, ValueError) else type(error).__name__, file=sys.stderr)
        return 2
    finally:
        if historical_hashes() != before:
            raise RuntimeError("Historical artifact integrity check failed")


if __name__ == "__main__":
    raise SystemExit(main())
