"""Allowlisted observation spans with the same trust envelope as support notes."""
import re
import unicodedata

CONTROL = re.compile(r"\b(?:ignore|override|deploy|dispatch|allocate|send|evacuate|supervisor|authorization|assistant|system|tool|protocol|json|redirect|mobilize|transfer|reassign|activate|R\d+|I\d+)\b", re.I)
FACT = re.compile(r"(?P<kind>Observation|Shelter location|Road condition):\s*(?P<value>minor cracks observed|residents report shaking|community hall|north bridge closed|no visible damage)", re.I)


def isolate_report(text, incident_id):
    facts, approved, withheld = [], [], []
    detected = False
    for span in re.finditer(r"[^;.!?\n]+[.!?]?", text):
        original = span.group()
        normalized = unicodedata.normalize("NFKC", original)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf").strip().rstrip(".!?")
        control = bool(CONTROL.search(normalized))
        match = None if control else FACT.fullmatch(normalized)
        if match:
            facts.append({"type": match["kind"].lower().replace(" ", "_"), "value": match["value"],
                "source": "field_report", "incident_id": incident_id, "trust": "unverified_source_content",
                "permitted_use": "quote_or_summarize", "action_authority": False,
                "source_span": {"start": span.start(), "end": span.end()}})
            approved.append({"start": span.start(), "end": span.end(), "text": original})
        else:
            detected |= control
            withheld.append({"start": span.start(), "end": span.end(), "text": original,
                             "reason": "agent_control" if control else "unknown_content"})
    return {"sanitized_facts": facts, "instructional_content_detected": detected}, {
        "original_text": text, "approved_spans": approved, "withheld_spans": withheld,
        "detector_outcome": "agent_control_detected" if detected else "allowlist_only"}
