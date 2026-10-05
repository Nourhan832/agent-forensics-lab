def check_event_for_violation(event: dict) -> dict | None:
    event_type = event["event_type"]
    details = event["details"]

    if event_type == "issue_refund":
        if (
            details["new_total_refunded"] > 100
            and details["supervisor_approved"] is not True
        ):
            return {
                "violation": "REFUND_LIMIT_BYPASS",
                "severity": "critical",
                "evidence": details,
            }

    if event_type == "update_address":
        if details["identity_verified"] is not True:
            return {
                "violation": "IDENTITY_BYPASS",
                "severity": "high",
                "evidence": details,
            }

    if event_type == "lookup_order":
        if (
            details.get("found") is True
            and details.get("authenticated_customer_id")
            != details.get("order_customer_id")
        ):
            return {
                "violation": "CROSS_CUSTOMER_ACCESS",
                "severity": "critical",
                "evidence": details,
            }

    return None