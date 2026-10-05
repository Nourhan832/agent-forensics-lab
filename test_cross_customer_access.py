"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.sandbox.state import SandboxState
    from backend.app.sandbox.tools import lookup_order
    from backend.app.evaluation.oracle import evaluate_events

    state = SandboxState(authenticated_customer_id="C001")

    print("\n--- LOOKUP OTHER CUSTOMER ORDER ---")
    print(lookup_order(state, "O2001"))

    print("\n--- EVENTS ---")
    for event in state.events:
        print(event)

    print("\n--- VIOLATIONS ---")
    violations = evaluate_events(state.events)

    for violation in violations:
        print(violation)

if __name__ == "__main__":
    main()
