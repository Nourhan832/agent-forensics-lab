"""Explicit provider smoke check: python -m backend.app.integrations.nebius_client."""
from backend.app.integrations.nemotron import generate_response


def main():
    try:
        response = generate_response(
            system_prompt="You are a concise AI assistant.",
            user_prompt="Reply with exactly: Nemotron wrapper working",
        )
        print("Provider smoke check:", "PASS" if response.strip() == "Nemotron wrapper working" else "REVIEW")
    except Exception as error:
        print(f"Provider smoke check failed ({type(error).__name__}); check configuration/connectivity.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
