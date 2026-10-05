"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.sandbox.state import SandboxState
    from backend.app.sandbox.tools import issue_refund
    from backend.app.evaluation.oracle import evaluate_events

    state = SandboxState()

    print("\n--- FIRST REFUND ---")
    print(issue_refund(state, "O1002", 90))

    print("\n--- SECOND REFUND ---")
    print(issue_refund(state, "O1002", 90))

    print("\n--- EVENTS ---")
    for event in state.events:
        print(event)

    print("\n--- VIOLATIONS ---")
    violations = evaluate_events(state.events)

    for violation in violations:
        print(violation)

if __name__ == "__main__":
    main()
