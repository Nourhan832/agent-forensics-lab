"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    CATEGORIES = [
        "authorization_bypass",
        "identity_bypass",
        "cross_customer_data_access",
        "indirect_prompt_injection",
        "false_action_claim",
    ]

    TESTS_PER_CATEGORY = 5

    all_results = []

    for category in CATEGORIES:
        print("\n" + "=" * 70)
        print(f"CATEGORY: {category}")
        print("=" * 70)

        category_results = []

        for i in range(TESTS_PER_CATEGORY):
            print(f"\n--- TEST {i + 1}/{TESTS_PER_CATEGORY} ---")

            result = run_forensics(category)
            category_results.append(result)
            all_results.append(result)

            print("\nAttack:")
            pprint(result["attack"])

            print("\nAgent result:")
            pprint(result["agent_result"])

            print("\nViolations:")
            pprint(result["violations"])

            print("\nOutcome:")
            if result["failed"]:
                print("❌ FAILED")
            else:
                print("✅ PASSED")

        failures = [
            result
            for result in category_results
            if result["failed"]
        ]

        print("\nCATEGORY SUMMARY")
        print(f"Total: {len(category_results)}")
        print(f"Passed: {len(category_results) - len(failures)}")
        print(f"Failed: {len(failures)}")


    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    total_failures = [
        result
        for result in all_results
        if result["failed"]
    ]

    print(f"Total tests: {len(all_results)}")
    print(f"Passed: {len(all_results) - len(total_failures)}")
    print(f"Failed: {len(total_failures)}")

    if total_failures:
        print("\nFIRST FAILURE FOUND:")
        pprint(total_failures[0])
    else:
        print("\nNo failures found across all categories.")

if __name__ == "__main__":
    main()
