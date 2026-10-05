"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    for attempt in range(5):
        result = run_forensics(
            "indirect_prompt_injection"
        )

        print(f"\n--- RUN {attempt + 1} ---")

        print("\nATTACK:")
        pprint(result["attack"])

        print("\nVIOLATIONS:")
        pprint(result["violations"])

        print("\nCRITICAL STEPS:")
        pprint(result["critical_steps"])

        print("\nFINGERPRINTS:")
        pprint(result["fingerprints"])

        print("\nFAILED:")
        print(result["failed"])

if __name__ == "__main__":
    main()
