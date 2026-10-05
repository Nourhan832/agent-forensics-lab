"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    for attempt in range(10):
        result = run_forensics(
            "cross_customer_data_access"
        )

        if result["failed"]:
            print("\n--- FAILURE FOUND ---")
            pprint(result["attack"])

            print("\n--- FAILURE FINGERPRINT ---")
            pprint(result["fingerprints"][0])

            break

    else:
        print("No failure found.")

if __name__ == "__main__":
    main()
