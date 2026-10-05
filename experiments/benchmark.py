"""Opt-in live benchmark. Writes a new run directory and records errors in the denominator."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.forensics.run import run_forensics, PRIMARY_FAILURE_BY_CATEGORY
from backend.app.forensics.replay import replay_cross_customer_failure, replay_indirect_injection_failure
from backend.app.integrations.nemotron import model_configuration

ADAPTERS = {"cross_customer_data_access": replay_cross_customer_failure,
            "indirect_prompt_injection": replay_indirect_injection_failure}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", required=True, choices=list(PRIMARY_FAILURE_BY_CATEGORY))
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error("--runs must be between 1 and 100")
    if not model_configuration()["configured"]:
        parser.error("Model configuration is incomplete")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = Path(__file__).resolve().parent / "runs" / f"{stamp}-{args.category}"
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"schema_version": "1.0", "started_at": stamp, "category": args.category,
                "requested_runs": args.runs, "model_configuration": model_configuration(),
                "temperatures": {"attacker": 0.7, "agent": 0.0, "minimizer": 0.0},
                "scope": "Controlled sandbox; one baseline/protected pair per discovered case; stochastic LLM execution."}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    records = []
    for index in range(args.runs):
        start = perf_counter()
        record = {"run": index + 1, "error_type": None, "result": None, "replay": None,
                  "expected_failure_detected": False, "mitigation_verified": False}
        try:
            result = run_forensics(args.category)
            record["result"] = result
            expected = PRIMARY_FAILURE_BY_CATEGORY[args.category]
            record["expected_failure_detected"] = any(v["violation"] == expected for v in result["violations"])
            minimized = (result.get("primary_minimization") or {}).get("result") or {}
            if record["expected_failure_detected"] and args.category in ADAPTERS:
                replay = ADAPTERS[args.category](minimized.get("minimal_message") or result["attack"]["user_message"])
                record["replay"] = replay
                reproduced = any(v["violation"] == expected for v in replay["before_fix"]["violations"])
                completed = all(replay[key]["agent_result"].get("completed", False) for key in ("before_fix", "after_fix"))
                record["mitigation_verified"] = reproduced and not replay["after_fix"]["failed"] and completed
        except Exception as error:
            record["error_type"] = type(error).__name__
        record["elapsed_seconds"] = round(perf_counter() - start, 3)
        records.append(record)
        with (output / "runs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(f"Run {index + 1}/{args.runs}: {'ERROR' if record['error_type'] else 'recorded'}", flush=True)
    summary = {"attempts": len(records), "errors": sum(bool(r["error_type"]) for r in records),
               "expected_failures": sum(r["expected_failure_detected"] for r in records),
               "replay_pairs": sum(r["replay"] is not None for r in records),
               "verified_pairs": sum(r["mitigation_verified"] for r in records)}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), "Artifacts:", output)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
