"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    for i in range(5):
        print("\n" + "=" * 70)
        print(f"RUN {i + 1}")
        print("=" * 70)

        result = run_forensics(
            "indirect_prompt_injection"
        )

        print("\nATTACK:")
        pprint(result["attack"])

        print("\nFAILED:")
        print(result["failed"])

        print("\nVIOLATIONS:")
        pprint(result["violations"])

        print("\nMINIMIZATIONS:")
        pprint(result["primary_minimization"])

if __name__ == "__main__":
    main()
