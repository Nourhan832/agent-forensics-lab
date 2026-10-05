import hashlib
import json


def create_failure_fingerprint(
    attack: dict,
    violation: dict,
    critical_step: dict,
) -> dict:
    evidence = violation["evidence"]

    fingerprint = {
        "failure_class": violation["violation"],
        "severity": violation["severity"],
        "attack_category": attack["category"],
        "attack_goal": attack["goal"],
        "trigger_message": attack["user_message"],

        "critical_step": (
            critical_step["critical_event_type"]
        ),

        "critical_event_index": (
            critical_step["critical_event_index"]
        ),

        "authenticated_customer_id": (
            evidence.get(
                "authenticated_customer_id"
            )
        ),

        "resource_owner_id": (
            evidence.get("order_customer_id")
            or evidence.get("resource_owner_id")
        ),

        "resource_id": (
            evidence.get("order_id")
            or evidence.get("unsafe_order_id")
            or evidence.get("customer_id")
            or evidence.get("resource_id")
        ),

        "evidence": evidence,
    }

    # Add causal-source information for
    # indirect prompt injection.
    if (
        violation["violation"]
        == "INDIRECT_PROMPT_INJECTION"
    ):
        fingerprint.update(
            {
                "source_event_index": (
                    evidence.get(
                        "source_event_index"
                    )
                ),

                "source_resource_id": (
                    evidence.get(
                        "source_order_id"
                    ) or evidence.get("source_resource_id")
                ),

                "unsafe_event_index": (
                    evidence.get(
                        "unsafe_event_index"
                    )
                ),

                "unsafe_resource_id": (
                    evidence.get(
                        "unsafe_order_id"
                    )
                ),

                "retrieved_untrusted_content": (
                    evidence.get(
                        "retrieved_untrusted_content"
                    )
                ),
            }
        )

    fingerprint["scenario"] = attack.get("scenario", {})
    identity = {key: fingerprint.get(key) for key in (
        "failure_class", "critical_step", "authenticated_customer_id",
        "resource_owner_id", "resource_id", "source_resource_id", "scenario")}
    fingerprint["schema_version"] = "1.0"
    fingerprint["fingerprint_id"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return fingerprint
