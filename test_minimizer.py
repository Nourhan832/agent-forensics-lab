"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics
    from backend.app.forensics.minimizer import minimize_failure


    for attempt in range(10):
        result = run_forensics(
            "cross_customer_data_access"
        )

        if not result["failed"]:
            continue

        fingerprint = result["fingerprints"][0]

        print("\n--- ORIGINAL FAILURE ---")
        pprint(fingerprint)

        minimized = minimize_failure(
            original_message=fingerprint["trigger_message"],
            expected_violation=fingerprint["failure_class"],
        )

        print("\n--- MINIMIZATION RESULT ---")
        pprint(minimized)

        break

    else:
        print("No failure found.")

if __name__ == "__main__":
    main()
