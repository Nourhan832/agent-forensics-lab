"""Bounded domain verification through the existing forensic engine.

Creates a disposable regression database under its new output directory. The
customer working database, corpus and historical results are never written.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.agents.decisions import safe_evidence
from backend.app.domains.emergency_response.adapter import EmergencyResponseReplayAdapter
from backend.app.domains.emergency_response.snapshot import load_snapshot
from backend.app.forensics.run import investigate_with_adapter
from backend.app.integrations.nemotron import capture_usage
from experiments.final_eval import safe_configuration, git_commit
from experiments.final_eval_core import atomic_json, digest, run_lock, token_totals


def validate_corpus(corpus):
    if corpus.get("schema_version") != "1.0" or not corpus.get("cases"): raise ValueError("Invalid corpus")
    seen = set()
    for case in corpus["cases"]:
        if case["id"] in seen or case["domain"] != "emergency_response": raise ValueError("Invalid case")
        seen.add(case["id"])
        if case["expected_failure_class"] not in {"UNAUTHORIZED_RESOURCE_DISPATCH", "INDIRECT_PROMPT_INJECTION", "UNSUPPORTED_EMERGENCY_CLAIM", "FALSE_DISPATCH_CLAIM"}:
            raise ValueError("Unknown failure class")
        if not isinstance(case["prompt"], str) or not case["prompt"].strip(): raise ValueError("Missing prompt")
        EmergencyResponseReplayAdapter(case["scenario"])
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=7)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimize-rounds", type=int, default=0)
    args = parser.parse_args()
    if not 1 <= args.limit <= 7: parser.error("Only a bounded 1-7 case targeted run is supported")
    if not 0 <= args.minimize_rounds <= 1: parser.error("Use at most one targeted minimization round")
    corpus = validate_corpus(json.loads((ROOT/"experiments/corpora/emergency_response_v1.json").read_text()))
    cases = [c for c in corpus["cases"] if c["live"]][:args.limit]
    if args.dry_run:
        print(json.dumps({"validated_cases": len(corpus["cases"]), "targeted_cases": len(cases), "provider_calls": 0,
            "snapshot_id": load_snapshot()["snapshot_id"]}));return
    configuration = safe_configuration()
    if not configuration["configured"]: parser.error("Provider is not configured")
    output = (args.output or ROOT/"experiments/runs"/datetime.now().strftime("emergency-targeted-%Y%m%d-%H%M%S")).resolve()
    if output.parent != (ROOT/"experiments/runs").resolve() or not output.name.startswith("emergency-targeted-"):
        parser.error("Use a new emergency-targeted-* directory under experiments/runs")
    output.mkdir(parents=True, exist_ok=True)
    code_files = list((ROOT/"backend").rglob("*.py"))+[Path(__file__)]
    contract = {"corpus_digest": digest(corpus), "snapshot_digest": digest(load_snapshot()), "model_configuration": configuration,
        "source_digest": digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files}),
        "case_ids": [c["id"] for c in cases], "minimize_rounds": args.minimize_rounds, "git_commit": git_commit()}
    with run_lock(output):
        metadata_path = output/"metadata.json"
        if metadata_path.exists():
            if json.loads(metadata_path.read_text())["contract"] != contract: parser.error("Resume contract changed")
        else:
            atomic_json(metadata_path, {"schema_version": "1.0", "timestamp": datetime.now(timezone.utc).isoformat(), "contract": contract})
        # Import storage only after selecting an isolated path. No startup of the API.
        from backend.app.storage import regressions as storage
        storage.DATABASE_PATH = output/"regressions.db"
        storage.initialize_regression_storage()
        records = []
        for case in cases:
            path = output/f"{case['id']}.json"
            if path.exists():
                records.append(json.loads(path.read_text()));continue
            adapter = EmergencyResponseReplayAdapter(case["scenario"])
            with capture_usage() as calls:
                report = investigate_with_adapter(adapter, case["prompt"], case["expected_failure_class"], case["category"], args.minimize_rounds)
            record = safe_evidence({"case": case, "report": report, "model_calls": calls, "usage": token_totals(calls), "estimated_cost_usd": None})
            replay_id = digest({"case": case["id"], "contract": contract})
            storage.save_replay_run(replay_id, case["category"], record)
            if report["verification"]["mitigation_verified"] is True:
                replay = report["replay"]
                saved = storage.save_regression_case(case["category"], case["expected_failure_class"], case["prompt"], replay["trigger"],
                    adapter.guardrail, "verified", True, replay["before_fix"]["violations"], replay["after_fix"]["violations"], scenario=adapter.scenario)
                record["regression_id"] = saved["id"]
            atomic_json(path, record)
            records.append(record)
            print(case["id"], json.dumps(report["verification"]), flush=True)
        summary = {"attempted": len(records), "completed": sum(r["report"]["verification"]["completed"] for r in records),
            "reproduced": sum(r["report"]["verification"]["reproduced"] for r in records),
            "mitigations_verified": sum(r["report"]["verification"]["mitigation_verified"] is True for r in records),
            "protected_utility_passes": sum(r["report"]["verification"]["utility_success"] for r in records),
            "provider_errors": sum(bool(call["error_type"]) for r in records for call in r["model_calls"]), "estimated_cost_usd": None}
        atomic_json(output/"summary.json", summary)
    print(str(output))


if __name__ == "__main__": main()
