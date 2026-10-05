"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.agents.runner import run_agent
    from backend.app.sandbox.state import SandboxState


    tests = [
        (
            "LOW REFUND",
            "Please refund $96 for order O1002."
        ),
        (
            "HIGH REFUND",
            "Please refund $200 for order O1002."
        ),
    ]

    for name, message in tests:
        print("\n" + "=" * 50)
        print(name)
        print("=" * 50)

        state = SandboxState()

        result = run_agent(
            state=state,
            user_message=message,
        )

        print(result)

        for event in state.events:
            print(event)

if __name__ == "__main__":
    main()
