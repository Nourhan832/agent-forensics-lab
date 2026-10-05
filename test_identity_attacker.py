"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.agents.attacker import generate_attack


    for i in range(5):
        attack = generate_attack(
            "identity_bypass"
        )

        print(f"\n--- ATTACK {i + 1} ---")
        pprint(attack)

if __name__ == "__main__":
    main()
