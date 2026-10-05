"""Legacy live experiment. Explicit invocation writes a new timestamped directory."""

def main():
    from datetime import datetime, timezone
    import sys
    import csv
    import json
    from pathlib import Path


    # ---------------------------------------------------------
    # Make project root importable
    # ---------------------------------------------------------

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


    from backend.app.forensics.run import run_forensics


    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    CATEGORY = "false_action_claim"
    EXPECTED_FAILURE = "FALSE_SUCCESS_CLAIM"
    NUM_RUNS = 20


    # ---------------------------------------------------------
    # Output
    # ---------------------------------------------------------

    OUTPUT_DIR = PROJECT_ROOT / "experiments" / "runs" / ("legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = (
        OUTPUT_DIR
        / "false_action_claim_experiment.json"
    )

    csv_path = (
        OUTPUT_DIR
        / "false_action_claim_experiment.csv"
    )


    # ---------------------------------------------------------
    # Run experiment
    # ---------------------------------------------------------

    results = []


    for i in range(NUM_RUNS):
        print("\n" + "=" * 70)
        print(f"RUN {i + 1}/{NUM_RUNS}")
        print("=" * 70)

        result = run_forensics(
            CATEGORY
        )

        false_claim = next(
            (
                violation
                for violation in result["violations"]
                if violation["violation"]
                == EXPECTED_FAILURE
            ),
            None,
        )

        false_claim_detected = (
            false_claim is not None
        )

        print("\nAttack:")
        print(
            result["attack"]["user_message"]
        )

        print("\nFinal response:")
        print(
            result["agent_result"]["final_response"]
        )

        print(
            "\nFalse success claim:",
            (
                "DETECTED"
                if false_claim_detected
                else "NOT DETECTED"
            ),
        )

        results.append(
            {
                "run": i + 1,
                "category": CATEGORY,
                "attack": result["attack"],
                "final_response": (
                    result[
                        "agent_result"
                    ]["final_response"]
                ),
                "events": result["events"],
                "violations": result["violations"],
                "false_success_claim": (
                    false_claim_detected
                ),
            }
        )


    # ---------------------------------------------------------
    # Save JSON
    # ---------------------------------------------------------

    with open(
        json_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )


    # ---------------------------------------------------------
    # Build CSV
    # ---------------------------------------------------------

    csv_rows = []

    for record in results:
        failed_refund_events = [
            event
            for event in record["events"]
            if event["event_type"]
            == "issue_refund_failed"
        ]

        csv_rows.append(
            {
                "run": record["run"],
                "category": record["category"],
                "user_message": (
                    record[
                        "attack"
                    ]["user_message"]
                ),
                "final_response": (
                    record["final_response"]
                ),
                "refund_failure_events": (
                    len(
                        failed_refund_events
                    )
                ),
                "false_success_claim": (
                    record[
                        "false_success_claim"
                    ]
                ),
            }
        )


    fieldnames = [
        "run",
        "category",
        "user_message",
        "final_response",
        "refund_failure_events",
        "false_success_claim",
    ]


    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(csv_rows)


    # ---------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------

    total_runs = len(results)

    false_claims = [
        record
        for record in results
        if record["false_success_claim"]
    ]

    safe_runs = [
        record
        for record in results
        if not record[
            "false_success_claim"
        ]
    ]


    false_claim_rate = (
        len(false_claims)
        / total_runs
        if total_runs
        else 0
    )


    safe_handling_rate = (
        len(safe_runs)
        / total_runs
        if total_runs
        else 0
    )


    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("FALSE ACTION CLAIM EXPERIMENT SUMMARY")
    print("=" * 70)

    print(
        f"Total runs: {total_runs}"
    )

    print(
        f"False success claims: "
        f"{len(false_claims)}"
    )

    print(
        f"False success claim rate: "
        f"{false_claim_rate:.2%}"
    )

    print(
        f"Correctly handled failures: "
        f"{len(safe_runs)}"
    )

    print(
        f"Safe handling rate: "
        f"{safe_handling_rate:.2%}"
    )

    print("\nSaved results:")
    print(json_path)
    print(csv_path)

if __name__ == "__main__":
    main()
