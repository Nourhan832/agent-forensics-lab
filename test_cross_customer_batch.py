"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    CATEGORY = "cross_customer_data_access"
    NUM_TESTS = 5

    results = []

    for i in range(NUM_TESTS):
        print("\n" + "=" * 60)
        print(f"TEST {i + 1}/{NUM_TESTS}")
        print("=" * 60)

        result = run_forensics(CATEGORY)
        results.append(result)

        print("\nAttack:")
        pprint(result["attack"])

        print("\nAgent result:")
        pprint(result["agent_result"])

        print("\nEvents:")
        pprint(result["events"])

        print("\nViolations:")
        pprint(result["violations"])

        print("\nCritical steps:")
        pprint(result["critical_steps"])

        print("\nOutcome:")
        if result["failed"]:
            print("❌ FAILED")
        else:
            print("✅ PASSED")


    failures = [r for r in results if r["failed"]]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"Total: {len(results)}")
    print(f"Passed: {len(results) - len(failures)}")
    print(f"Failed: {len(failures)}")

    if failures:
        print("\nFIRST CONFIRMED FAILURE:")
        pprint(failures[0])

if __name__ == "__main__":
    main()
