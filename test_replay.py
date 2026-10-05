"""Manual demo/check; may make paid model calls when run explicitly."""

def main():
    from pprint import pprint

    from backend.app.forensics.replay import replay_failure


    trigger = "O2001"

    result = replay_failure(trigger)

    print("\n--- TRIGGER ---")
    print(result["trigger"])

    print("\n--- BEFORE FIX ---")
    pprint(result["before_fix"])

    print("\n--- AFTER FIX ---")
    pprint(result["after_fix"])

    print("\n--- SUMMARY ---")

    if result["before_fix"]["failed"]:
        print("Before fix: ❌ FAIL")
    else:
        print("Before fix: ✅ PASS")

    if result["after_fix"]["failed"]:
        print("After fix: ❌ FAIL")
    else:
        print("After fix: ✅ PASS")

if __name__ == "__main__":
    main()
