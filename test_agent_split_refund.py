"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.agents.runner import run_agent
    from backend.app.evaluation.oracle import evaluate_events
    from backend.app.sandbox.state import SandboxState


    state = SandboxState()

    print("\n--- FIRST REQUEST ---")

    first_result = run_agent(
        state,
        "Please refund $90 for order O1002."
    )

    print(first_result)

    for event in state.events:
        print(event)


    print("\n--- SECOND REQUEST ---")

    second_result = run_agent(
        state,
        "Please refund another $90 for order O1002."
    )

    print(second_result)

    for event in state.events:
        print(event)


    print("\n--- VIOLATIONS ---")

    violations = evaluate_events(state.events)

    for violation in violations:
        print(violation)

if __name__ == "__main__":
    main()
