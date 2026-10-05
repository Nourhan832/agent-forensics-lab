"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    for i in range(3):
        print("\n" + "=" * 70)
        print(f"RUN {i + 1}")
        print("=" * 70)

        result = run_forensics(
            "indirect_prompt_injection"
        )

        print("\nFAILED:")
        print(result["failed"])

        print("\nEXPECTED PRIMARY FAILURE:")
        print(
            result["expected_primary_failure"]
        )

        print("\nPRIMARY VIOLATION:")
        pprint(
            result["primary_violation"]
        )

        print("\nALL VIOLATIONS:")
        pprint(
            [
                violation["violation"]
                for violation
                in result["violations"]
            ]
        )

        print("\nPRIMARY MINIMIZATION:")
        pprint(
            result["primary_minimization"]
        )

if __name__ == "__main__":
    main()
