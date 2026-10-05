"""Read-only historical artifact audit; no model calls or result overwrites."""
import csv
import json
import math
from pathlib import Path


def wilson_interval(successes, total):
    if not total:
        return None
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0, 100 * (center - half)), 2), round(min(100, 100 * (center + half)), 2)]


def summarize(directory=None):
    directory = directory or Path(__file__).resolve().parent / "results"
    summaries = []
    keys = {"cross_customer_experiment": "failure_detected",
            "indirect_prompt_injection_experiment": "expected_failure_detected",
            "identity_bypass_experiment": "identity_bypass",
            "false_action_claim_experiment": "false_success_claim"}
    for name, failure_key in keys.items():
        with (directory / (name + ".csv")).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        records = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
        if len(rows) != len(records):
            raise ValueError(f"CSV/JSON run count mismatch: {name}")
        failures = sum(row[failure_key] == "True" for row in rows)
        # Check findings against the complete JSON, independently of the summary flag.
        expected = {"cross_customer_experiment": "CROSS_CUSTOMER_ACCESS",
                    "indirect_prompt_injection_experiment": "INDIRECT_PROMPT_INJECTION",
                    "identity_bypass_experiment": "IDENTITY_BYPASS",
                    "false_action_claim_experiment": "FALSE_SUCCESS_CLAIM"}[name]
        json_failures = sum(any(v["violation"] == expected for v in record["violations"]) for record in records)
        if json_failures != failures:
            raise ValueError(f"CSV/JSON finding count mismatch: {name}")
        reductions = [float(row["reduction_percent"]) for row in rows if row.get("reduction_percent")]
        before_key = "reproduced_before_fix" if "injection" in name else "before_fix_failed"
        after_key = "expected_failure_after_fix" if "injection" in name else "after_fix_failed"
        replayed = [row for row in rows if row.get(before_key) in {"True", "False"}]
        summaries.append({"artifact": name, "runs": len(rows), "failures": failures,
                          "observed_failure_percent": round(100 * failures / len(rows), 2),
                          "illustrative_95_percent_wilson_interval": wilson_interval(failures, len(rows)),
                          "minimization_records": len(reductions),
                          "average_word_reduction_percent": round(sum(reductions) / len(reductions), 2) if reductions else None,
                          "baseline_reproduced": sum(row[before_key] == "True" for row in replayed),
                          "protected_no_expected_violation": sum(row[after_key] == "False" for row in replayed),
                          "replay_records": len(replayed)})
    return {"scope": "Historical controlled sandbox observations. Wilson intervals assume independent Bernoulli trials; generated prompts may be correlated.",
            "model_provenance": "Not recorded in historical artifacts; model version cannot be independently reconstructed.",
            "experiments": summaries}


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
