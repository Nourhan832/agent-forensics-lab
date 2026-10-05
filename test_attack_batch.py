"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    CATEGORY = "authorization_bypass"
    NUM_TESTS = 10

    results = []

    for i in range(NUM_TESTS):
        print(f"\n{'=' * 50}")
        print(f"TEST {i + 1}/{NUM_TESTS}")
        print(f"{'=' * 50}")

        result = run_forensics(CATEGORY)

        results.append(result)

        print("\nAttack:")
        pprint(result["attack"])

        print("\nAgent result:")
        pprint(result["agent_result"])

        print("\nViolations:")
        pprint(result["violations"])

        print("\nResult:")
        if result["failed"]:
            print("❌ FAILED")
        else:
            print("✅ PASSED")


    failed_runs = [
        result
        for result in results
        if result["failed"]
    ]

    print("\n\n===================================")
    print("BATCH SUMMARY")
    print("===================================")

    print(f"Total tests: {len(results)}")
    print(f"Passed: {len(results) - len(failed_runs)}")
    print(f"Failed: {len(failed_runs)}")

    if failed_runs:
        print("\nFIRST FAILURE FOUND:")
        pprint(failed_runs[0])
    else:
        print("\nNo failures found in this batch.")

if __name__ == "__main__":
    main()
