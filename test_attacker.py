"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from backend.app.agents.attacker import generate_attack


    attack = generate_attack("authorization_bypass")

    print("\n--- GENERATED ATTACK ---")
    print(attack)

if __name__ == "__main__":
    main()
