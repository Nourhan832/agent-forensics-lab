"""Conservative local extraction. Unknown text is withheld, never promoted to authority."""
import re
import unicodedata

VERSION = "business-facts-1"
TIME = r"(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:AM|PM)|noon|midnight"
PLACE = r"(?:the\s+)?(?:(?:blue|red|green|front|rear|side|main|reception)\s+){0,3}(?:desk|entrance|door|office|locker)"
RULES = [
    ("delivery_window", re.compile(rf"Delivery window:\s*(?P<value>(?:{TIME})\s+(?:to|until)\s+(?:{TIME}))", re.I)),
    ("collection_location", re.compile(rf"Collection point:\s*(?P<value>{PLACE})", re.I)),
    ("packing_preference", re.compile(r"Packing note:\s*(?P<value>include (?:the )?(?:printed receipt|receipt|packing slip))", re.I)),
    ("delivery_preference", re.compile(rf"Delivery preference:\s*(?P<value>ring (?:the\s+)?(?:(?:side|front|rear|main)\s+)?(?:entrance\s+)?bell)", re.I)),
]
CONTROL = re.compile(r"\b(?:[OC]\d+|lookup|look\s+up|cross[-\s]?check|related\s+order|customer|account|record|consult|fetch|retrieve|policy|override|ignore|system|assistant|developer|tool|json|protocol|reveal|disclose|refund|supervisor|authorization|authorised|authorized)\b", re.I)


def extract_business_facts(notes, order_id):
    facts, approved, withheld = [], [], []
    detected = False
    # Offsets always reference the original text; normalization is detection-only.
    for match in re.finditer(r"[^\n;.!?]+[.!?]?", notes or ""):
        original = match.group()
        text = unicodedata.normalize("NFKC", original)
        text = "".join(c for c in text if unicodedata.category(c) != "Cf")
        text = " ".join(text.strip().rstrip(".!?").split())
        if not text:
            continue
        control = bool(CONTROL.search(text))
        accepted = None
        if not control:
            for kind, pattern in RULES:
                parsed = pattern.fullmatch(text)
                if parsed:
                    accepted = {"type": kind, "value": parsed["value"], "source": "order_notes",
                                "resource_id": order_id, "source_span": {"start": match.start(), "end": match.end()},
                                "trust": "unverified_source_content", "permitted_use": "quote_or_summarize",
                                "action_authority": False, "extractor_version": VERSION}
                    break
        if accepted:
            facts.append(accepted)
            approved.append({"start": match.start(), "end": match.end(), "text": original, "fact_type": accepted["type"]})
        else:
            detected |= control
            withheld.append({"start": match.start(), "end": match.end(), "text": original,
                             "reason": "agent_control_instruction" if control else "unrecognized_business_content"})
    return facts, {"extractor_version": VERSION, "approved_spans": approved, "withheld_spans": withheld,
                   "instructional_content_detected": detected,
                   "detector_outcome": "agent_control_detected" if detected else ("unknown_content_withheld" if withheld else "approved_business_facts_only")}


def exposed_untrusted_content(event):
    """Use the actual tool view before legacy flags; isolation=True alone proves nothing."""
    order = event.get("result", {}).get("order")
    if isinstance(order, dict):
        return bool(order.get("notes") or order.get("retrieved_content", {}).get("sanitized_facts"))
    view = event.get("details", {}).get("agent_visible_content")
    if view is not None:
        return bool(view.get("untrusted_text") or view.get("sanitized_facts"))
    details = event.get("details", {})
    return details.get("contains_untrusted_content") is True and details.get("content_isolated") is not True
