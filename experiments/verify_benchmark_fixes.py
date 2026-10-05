"""Run ONLY the eight reviewed cases, selected in memory from the frozen corpus."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.final_eval import DEFAULT_CORPUS, run_cases, safe_configuration, source_hash
from experiments.final_eval_core import ROOT, SCHEMA_VERSION, digest, historical_hashes, historical_prompts, read_json, validate_corpus

CASE_IDS = [f"indirect_prompt_injection-{n}" for n in ("02", "03", "07", "10")] + [f"benign-{n}" for n in range(37, 41)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    frozen = read_json(DEFAULT_CORPUS)
    validate_corpus(frozen, forbidden_prompts=historical_prompts())
    by_id = {c["id"]: c for c in frozen["cases"]}
    corpus = {**frozen, "cases": [by_id[cid] for cid in CASE_IDS]}
    validate_corpus(corpus, require_target=False)
    if args.dry_run:
        print(json.dumps({"selected_cases": CASE_IDS, "planned_prompts": 8, "provider_calls": 0, "frozen_corpus_digest": digest(frozen)}, indent=2))
        return 0
    config = safe_configuration()
    if not config["configured"]:
        raise ValueError("Provider configuration is incomplete")
    contract = {"schema_version": SCHEMA_VERSION, "corpus_id": frozen["corpus_id"],
                "corpus_digest": digest(frozen), "selected_case_ids": CASE_IDS,
                "selected_corpus_digest": digest(corpus), "source_digest": source_hash(),
                "verification_runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "python_version": platform.python_version(), "model_configuration": config,
                "minimize_rounds": 1, "pricing": None, "targeted_verification_only": True,
                "historical_artifacts_sha256": historical_hashes()}
    output = args.output or ROOT / "experiments" / "runs" / ("targeted-fixes-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ"))
    before = historical_hashes()
    try:
        summary = run_cases(output, corpus, contract)
        print(json.dumps({"output": str(output.resolve()), "evaluated_prompts": summary["evaluated_prompts"],
                          "errors": summary["error_cases"], "total_tokens": summary["total_tokens"], "estimated_cost_usd": None}))
        return 1 if summary["error_cases"] else 0
    finally:
        if historical_hashes() != before:
            raise RuntimeError("Historical artifact integrity check failed")


if __name__ == "__main__":
    raise SystemExit(main())
