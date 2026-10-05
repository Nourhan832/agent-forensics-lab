"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    for i in range(5):
        result = run_forensics(
            "identity_bypass"
        )

        print(f"\n{'=' * 70}")
        print(f"RUN {i + 1}")
        print("=" * 70)

        print("\nATTACK:")
        pprint(result["attack"])

        print("\nFINAL RESPONSE:")
        pprint(
            result["agent_result"]["final_response"]
        )

        print("\nEVENTS:")
        pprint(result["events"])

        print("\nVIOLATIONS:")
        pprint(result["violations"])

        print("\nFAILED:")
        print(result["failed"])

if __name__ == "__main__":
    main()
