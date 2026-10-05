def localize_critical_steps(
    events: list[dict],
    violations: list[dict],
) -> list[dict]:
    findings = []

    for violation in violations:
        event_index = violation["event_index"]
        if not isinstance(event_index, int) or not 0 <= event_index < len(events):
            raise ValueError("Finding does not reference a recorded event.")
        event = events[event_index]

        finding = {
            "critical_event_index": event_index,
            "critical_event_type": event["event_type"],
            "violation": violation["violation"],
            "severity": violation["severity"],
            "details": event["details"],
        }

        # Indirect prompt injection has both:
        # 1. the poisoned source retrieval
        # 2. the later unsafe action
        if violation["violation"] == "INDIRECT_PROMPT_INJECTION":
            evidence = violation["evidence"]

            source_index = evidence.get(
                "source_event_index"
            )

            if (
                source_index is not None
                and 0 <= source_index < len(events)
            ):
                source_event = events[source_index]

                finding["source_event_index"] = (
                    source_index
                )

                finding["source_event_type"] = (
                    source_event["event_type"]
                )

                finding["source_event_details"] = (
                    source_event["details"]
                )

            finding["unsafe_event_index"] = (
                evidence.get("unsafe_event_index")
            )

            finding["unsafe_order_id"] = (
                evidence.get("unsafe_order_id")
            )

        findings.append(finding)

    return findings
