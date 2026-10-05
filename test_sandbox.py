"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.sandbox.state import SandboxState
    from backend.app.evaluation.oracle import evaluate_events
    from backend.app.forensics.localizer import localize_critical_steps
    from backend.app.sandbox.tools import (
        lookup_customer,
        lookup_order,
        check_supervisor_approval,
        issue_refund,
        update_address,
    )

    state = SandboxState()

    print("\n--- CUSTOMER LOOKUP ---")
    print(lookup_customer(state, "C001"))

    print("\n--- ORDER LOOKUP ---")
    print(lookup_order(state, "O1002"))

    print("\n--- SUPERVISOR APPROVAL ---")
    print(check_supervisor_approval(state, "O1002"))

    print("\n--- UNSAFE REFUND TEST ---")
    print(issue_refund(state, "O1002", 480.0))

    print("\n--- ADDRESS UPDATE TEST ---")
    print(update_address(state, "C002", "99 New Street"))

    print("\n--- EVENT LOG ---")
    for event in state.events:
        print(event)
    print("\n--- POLICY VIOLATIONS ---")

    violations = evaluate_events(state.events)

    for violation in violations:
        print(violation)
    print("\n--- CRITICAL STEPS ---")

    critical_steps = localize_critical_steps(
        state.events,
        violations,
    )

    for finding in critical_steps:
        print(finding)

if __name__ == "__main__":
    main()
