"""Legacy live experiment. Explicit invocation writes a new timestamped directory."""

def main():
    from datetime import datetime, timezone
    import sys
    import csv
    import json
    from pathlib import Path


    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


    from backend.app.forensics.run import run_forensics


    CATEGORY = "identity_bypass"
    EXPECTED_FAILURE = "IDENTITY_BYPASS"
    NUM_RUNS = 20


    OUTPUT_DIR = PROJECT_ROOT / "experiments" / "runs" / ("legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "identity_bypass_experiment.json"
    csv_path = OUTPUT_DIR / "identity_bypass_experiment.csv"


    results = []


    for i in range(NUM_RUNS):
        print("\n" + "=" * 70)
        print(f"RUN {i + 1}/{NUM_RUNS}")
        print("=" * 70)

        result = run_forensics(CATEGORY)

        identity_bypass = next(
            (
                violation
                for violation in result["violations"]
                if violation["violation"] == EXPECTED_FAILURE
            ),
            None,
        )

        bypass_detected = identity_bypass is not None

        update_events = [
            event
            for event in result["events"]
            if event["event_type"] == "update_address"
        ]

        print("\nAttack:")
        print(result["attack"]["user_message"])

        print("\nFinal response:")
        print(
            result["agent_result"]["final_response"]
        )

        print(
            "\nIdentity bypass:",
            "DETECTED" if bypass_detected else "NOT DETECTED",
        )

        print(
            "Address update executed:",
            "YES" if update_events else "NO",
        )

        results.append(
            {
                "run": i + 1,
                "category": CATEGORY,
                "attack": result["attack"],
                "final_response": (
                    result["agent_result"]["final_response"]
                ),
                "events": result["events"],
                "violations": result["violations"],
                "identity_bypass": bypass_detected,
                "address_update_executed": bool(update_events),
            }
        )


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


    csv_rows = []

    for record in results:
        csv_rows.append(
            {
                "run": record["run"],
                "category": record["category"],
                "user_message": (
                    record["attack"]["user_message"]
                ),
                "final_response": (
                    record["final_response"]
                ),
                "address_update_executed": (
                    record["address_update_executed"]
                ),
                "identity_bypass": (
                    record["identity_bypass"]
                ),
            }
        )


    fieldnames = [
        "run",
        "category",
        "user_message",
        "final_response",
        "address_update_executed",
        "identity_bypass",
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


    total_runs = len(results)

    bypass_failures = [
        record
        for record in results
        if record["identity_bypass"]
    ]

    safe_runs = [
        record
        for record in results
        if not record["identity_bypass"]
    ]

    executed_updates = [
        record
        for record in results
        if record["address_update_executed"]
    ]


    bypass_rate = (
        len(bypass_failures) / total_runs
        if total_runs
        else 0
    )

    safe_handling_rate = (
        len(safe_runs) / total_runs
        if total_runs
        else 0
    )


    print("\n" + "=" * 70)
    print("IDENTITY BYPASS EXPERIMENT SUMMARY")
    print("=" * 70)

    print(f"Total runs: {total_runs}")

    print(
        f"Identity bypass failures: "
        f"{len(bypass_failures)}"
    )

    print(
        f"Identity bypass rate: "
        f"{bypass_rate:.2%}"
    )

    print(
        f"Address updates executed: "
        f"{len(executed_updates)}"
    )

    print(
        f"Correctly handled requests: "
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
