"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.run import run_forensics


    result = run_forensics("authorization_bypass")

    print("\n==============================")
    print("AGENT FORENSICS LAB")
    print("==============================")

    print("\n--- GENERATED ATTACK ---")
    pprint(result["attack"])

    print("\n--- TARGET AGENT RESULT ---")
    pprint(result["agent_result"])

    print("\n--- EXECUTION TRACE ---")
    for index, event in enumerate(result["events"]):
        print(f"\nStep {index}:")
        pprint(event)

    print("\n--- POLICY VIOLATIONS ---")

    if result["violations"]:
        for violation in result["violations"]:
            pprint(violation)
    else:
        print("No violations detected.")

    print("\n--- CRITICAL STEPS ---")

    if result["critical_steps"]:
        for critical_step in result["critical_steps"]:
            pprint(critical_step)
    else:
        print("No critical failure steps detected.")

    print("\n--- FINAL RESULT ---")

    if result["failed"]:
        print(" AGENT FAILED THE TEST")
    else:
        print(" AGENT PASSED THE TEST")

if __name__ == "__main__":
    main()
