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
    from backend.app.forensics.minimizer import minimize_failure
    from backend.app.forensics.replay import (
        replay_indirect_injection_failure,
    )


    # ---------------------------------------------------------
    # Experiment configuration
    # ---------------------------------------------------------

    CATEGORY = "indirect_prompt_injection"
    EXPECTED_FAILURE = "INDIRECT_PROMPT_INJECTION"

    # Keep at 3 for the smoke test.
    # Change to 20 after confirming everything works.
    NUM_RUNS = 20


    # ---------------------------------------------------------
    # Output paths
    # ---------------------------------------------------------

    OUTPUT_DIR = PROJECT_ROOT / "experiments" / "runs" / ("legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = (
        OUTPUT_DIR
        / "indirect_prompt_injection_experiment.json"
    )

    csv_path = (
        OUTPUT_DIR
        / "indirect_prompt_injection_experiment.csv"
    )


    # ---------------------------------------------------------
    # Helper
    # ---------------------------------------------------------

    def contains_expected_violation(
        violations: list[dict],
    ) -> bool:
        return any(
            violation.get("violation") == EXPECTED_FAILURE
            for violation in violations
        )


    # ---------------------------------------------------------
    # Run experiment
    # ---------------------------------------------------------

    results = []


    for i in range(NUM_RUNS):
        print("\n" + "=" * 70)
        print(f"RUN {i + 1}/{NUM_RUNS}")
        print("=" * 70)

        forensic_result = run_forensics(
            CATEGORY
        )

        # Find the fingerprint specifically for
        # INDIRECT_PROMPT_INJECTION.
        fingerprint = next(
            (
                fp
                for fp in forensic_result["fingerprints"]
                if fp["failure_class"] == EXPECTED_FAILURE
            ),
            None,
        )

        expected_failure_detected = (
            fingerprint is not None
        )

        record = {
            "run": i + 1,
            "category": CATEGORY,
            "expected_failure": EXPECTED_FAILURE,

            "attack": forensic_result["attack"],

            "any_failure_detected": (
                forensic_result["failed"]
            ),

            "expected_failure_detected": (
                expected_failure_detected
            ),

            "violations": (
                forensic_result["violations"]
            ),

            "critical_steps": (
                forensic_result["critical_steps"]
            ),

            "fingerprints": (
                forensic_result["fingerprints"]
            ),

            "selected_fingerprint": (
                fingerprint
            ),

            "minimization": None,
            "replay": None,

            "reproduced_before_fix": None,
            "expected_failure_after_fix": None,
        }

        # -----------------------------------------------------
        # Expected failure occurred
        # -----------------------------------------------------

        if fingerprint is not None:
            print(
                "Failure found:",
                fingerprint["failure_class"],
            )

            # -------------------------------------------------
            # Minimize trigger
            # -------------------------------------------------

            minimization = minimize_failure(
                original_message=(
                    fingerprint["trigger_message"]
                ),
                expected_violation=(
                    fingerprint["failure_class"]
                ),
            )

            record["minimization"] = (
                minimization
            )

            minimal_message = (
                minimization["minimal_message"]
            )

            # -------------------------------------------------
            # Replay using injection-specific content isolation
            # -------------------------------------------------

            replay = replay_indirect_injection_failure(
                minimal_message
            )

            record["replay"] = replay

            before_violations = (
                replay["before_fix"]["violations"]
            )

            after_violations = (
                replay["after_fix"]["violations"]
            )

            reproduced_before_fix = (
                contains_expected_violation(
                    before_violations
                )
            )

            expected_failure_after_fix = (
                contains_expected_violation(
                    after_violations
                )
            )

            record["reproduced_before_fix"] = (
                reproduced_before_fix
            )

            record["expected_failure_after_fix"] = (
                expected_failure_after_fix
            )

            # -------------------------------------------------
            # Print run information
            # -------------------------------------------------

            print("\nOriginal trigger:")
            print(
                fingerprint["trigger_message"]
            )

            print("\nMinimal trigger:")
            print(
                minimal_message
            )

            print(
                "\nBefore fix:",
                (
                    "FAIL"
                    if reproduced_before_fix
                    else "PASS"
                ),
            )

            print(
                "After fix:",
                (
                    "FAIL"
                    if expected_failure_after_fix
                    else "PASS"
                ),
            )

            print("\nInjection source:")
            print(
                fingerprint.get(
                    "source_resource_id"
                )
            )

            print("Unsafe resource:")
            print(
                fingerprint.get(
                    "unsafe_resource_id"
                )
            )

            print(
                "Guardrail:",
                replay.get("guardrail"),
            )

        else:
            print(
                f"No confirmed "
                f"{EXPECTED_FAILURE} failure."
            )

        results.append(record)


    # ---------------------------------------------------------
    # Save full JSON results
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
    # Build CSV summary rows
    # ---------------------------------------------------------

    csv_rows = []


    for record in results:
        fingerprint = (
            record["selected_fingerprint"]
        )

        minimization = (
            record["minimization"]
        )

        replay = (
            record["replay"]
        )

        original_trigger = None
        minimal_trigger = None

        original_length = None
        minimal_length = None

        reduction_percent = None

        source_resource_id = None
        unsafe_resource_id = None

        source_event_index = None
        unsafe_event_index = None

        resource_owner_id = None

        guardrail = None


        # -----------------------------------------------------
        # Fingerprint information
        # -----------------------------------------------------

        if fingerprint is not None:
            original_trigger = (
                fingerprint[
                    "trigger_message"
                ]
            )

            original_length = len(
                original_trigger.split()
            )

            source_resource_id = (
                fingerprint.get(
                    "source_resource_id"
                )
            )

            unsafe_resource_id = (
                fingerprint.get(
                    "unsafe_resource_id"
                )
            )

            source_event_index = (
                fingerprint.get(
                    "source_event_index"
                )
            )

            unsafe_event_index = (
                fingerprint.get(
                    "unsafe_event_index"
                )
            )

            resource_owner_id = (
                fingerprint.get(
                    "resource_owner_id"
                )
            )


        # -----------------------------------------------------
        # Minimization information
        # -----------------------------------------------------

        if minimization is not None:
            minimal_trigger = (
                minimization[
                    "minimal_message"
                ]
            )

            minimal_length = len(
                minimal_trigger.split()
            )

            if (
                original_length is not None
                and original_length > 0
            ):
                reduction_percent = round(
                    (
                        (
                            original_length
                            - minimal_length
                        )
                        / original_length
                    )
                    * 100,
                    2,
                )


        # -----------------------------------------------------
        # Replay information
        # -----------------------------------------------------

        if replay is not None:
            guardrail = replay.get(
                "guardrail"
            )


        # -----------------------------------------------------
        # CSV row
        # -----------------------------------------------------

        csv_rows.append(
            {
                "run": (
                    record["run"]
                ),

                "category": (
                    record["category"]
                ),

                "expected_failure": (
                    record["expected_failure"]
                ),

                "expected_failure_detected": (
                    record[
                        "expected_failure_detected"
                    ]
                ),

                "failure_class": (
                    fingerprint["failure_class"]
                    if fingerprint
                    else None
                ),

                "original_trigger": (
                    original_trigger
                ),

                "minimal_trigger": (
                    minimal_trigger
                ),

                "original_words": (
                    original_length
                ),

                "minimal_words": (
                    minimal_length
                ),

                "reduction_percent": (
                    reduction_percent
                ),

                "source_resource_id": (
                    source_resource_id
                ),

                "unsafe_resource_id": (
                    unsafe_resource_id
                ),

                "source_event_index": (
                    source_event_index
                ),

                "unsafe_event_index": (
                    unsafe_event_index
                ),

                "resource_owner_id": (
                    resource_owner_id
                ),

                "guardrail": (
                    guardrail
                ),

                "reproduced_before_fix": (
                    record[
                        "reproduced_before_fix"
                    ]
                ),

                "expected_failure_after_fix": (
                    record[
                        "expected_failure_after_fix"
                    ]
                ),
            }
        )


    # ---------------------------------------------------------
    # Save CSV
    # ---------------------------------------------------------

    fieldnames = [
        "run",
        "category",
        "expected_failure",
        "expected_failure_detected",
        "failure_class",
        "original_trigger",
        "minimal_trigger",
        "original_words",
        "minimal_words",
        "reduction_percent",
        "source_resource_id",
        "unsafe_resource_id",
        "source_event_index",
        "unsafe_event_index",
        "resource_owner_id",
        "guardrail",
        "reproduced_before_fix",
        "expected_failure_after_fix",
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
    # Calculate experiment metrics
    # ---------------------------------------------------------

    total_runs = len(results)


    confirmed_failures = [
        record
        for record in results
        if record[
            "expected_failure_detected"
        ]
    ]


    minimized_failures = [
        row
        for row in csv_rows
        if row["minimal_trigger"]
        is not None
    ]


    reproduced_failures = [
        record
        for record in results
        if record[
            "reproduced_before_fix"
        ]
        is True
    ]


    fixed_failures = [
        record
        for record in results
        if (
            record[
                "reproduced_before_fix"
            ]
            is True
            and record[
                "expected_failure_after_fix"
            ]
            is False
        )
    ]


    attack_success_rate = (
        len(confirmed_failures)
        / total_runs
        if total_runs > 0
        else 0
    )


    reduction_values = [
        row["reduction_percent"]
        for row in minimized_failures
        if row["reduction_percent"]
        is not None
    ]


    average_reduction = (
        sum(reduction_values)
        / len(reduction_values)
        if reduction_values
        else 0
    )


    reproduction_rate = (
        len(reproduced_failures)
        / len(confirmed_failures)
        if confirmed_failures
        else 0
    )


    fix_rate = (
        len(fixed_failures)
        / len(reproduced_failures)
        if reproduced_failures
        else 0
    )


    # ---------------------------------------------------------
    # Print summary
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print(
        "INDIRECT PROMPT INJECTION "
        "EXPERIMENT SUMMARY"
    )
    print("=" * 70)


    print(
        f"Total runs: "
        f"{total_runs}"
    )


    print(
        f"Confirmed indirect injection failures: "
        f"{len(confirmed_failures)}"
    )


    print(
        f"Attack success rate: "
        f"{attack_success_rate:.2%}"
    )


    print(
        f"Minimized failures: "
        f"{len(minimized_failures)}"
    )


    print(
        f"Average trigger reduction: "
        f"{average_reduction:.2f}%"
    )


    print(
        f"Reproduced before fix: "
        f"{len(reproduced_failures)}"
    )


    print(
        f"Reproduction rate: "
        f"{reproduction_rate:.2%}"
    )


    print(
        f"Failures blocked by content isolation: "
        f"{len(fixed_failures)}"
    )


    print(
        f"Content-isolation fix rate: "
        f"{fix_rate:.2%}"
    )


    print("\nSaved results:")

    print(
        json_path
    )

    print(
        csv_path
    )

if __name__ == "__main__":
    main()
