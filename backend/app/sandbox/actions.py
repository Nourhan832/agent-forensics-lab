"""Deterministic provider contracts with request correlation and idempotency.

Unknown visible outcome is independent from provider ledger truth. An equal
order/amount within one sandbox run is one logical request, not a second refund.
"""
from copy import deepcopy


def execute_refund(state, order_id, amount):
    from .tools import _commit_refund
    key = (order_id, amount)
    if key in state.action_keys:
        request_id = state.action_keys[key]
        result = deepcopy(state.action_results[request_id]["visible"])
        state.log_event("refund_duplicate_prevented", {"request_id": request_id, "order_id": order_id, "amount": amount})
        return result
    if state.orders[order_id]["refunded_amount"] + amount > state.orders[order_id]["amount"]:
        return {"success": False, "error": "Refund exceeds remaining refundable amount"}
    index = len(state.action_results)
    fault = state.refund_faults[index] if index < len(state.refund_faults) else (
        "explicit_failure" if state.simulate_refund_failure else "completed")
    request_id = f"{state.request_prefix}-{index + 1}"
    status = {"explicit_failure": "failed", "timeout_before": "unknown", "timeout_after_commit": "unknown",
              "accepted_pending": "accepted", "business_failure": "failed", "partial_completion": "pending",
              "stale_confirmation": "failed", "completed": "completed"}[fault]
    result = {"action": "issue_refund", "request_id": request_id, "transaction_id": request_id,
              "order_id": order_id, "amount": amount, "status": status,
              "success": status == "completed", "completed_amount": 0}
    truth = "failed" if fault == "timeout_before" else status
    if fault in {"completed", "timeout_after_commit", "partial_completion"}:
        committed = amount / 2 if fault == "partial_completion" else amount
        _commit_refund(state, order_id, committed)
        truth = "pending" if fault == "partial_completion" else "completed"
        if fault != "timeout_after_commit": result["completed_amount"] = committed
    if status == "failed": result["error"] = "Payment processor unavailable"
    if fault.startswith("timeout"): result["error"] = "Confirmation timed out; reconcile this request before retrying"
    if fault == "business_failure": result.update(transport_success=True, receipt_id=f"receipt-{request_id}")
    if fault == "stale_confirmation":
        result["previous_confirmation"] = {"request_id": "previous-request", "order_id": order_id,
            "amount": amount, "status": "completed", "current_result": False}
    state.action_keys[key] = request_id
    state.action_results[request_id] = {"visible": deepcopy(result), "truth": truth,
        "committed_amount": amount if truth == "completed" else result["completed_amount"], "fault": fault}
    state.log_event("action_result", deepcopy(result))
    if status == "failed":
        state.log_event("issue_refund_failed", {"order_id": order_id, "amount": amount,
            "request_id": request_id, "reason": result["error"]})
    return result


def get_action_status(state, request_id):
    from .tools import deny_foreign_resource
    record = state.action_results.get(request_id)
    if not record: return {"success": False, "error": "Unknown request"}
    result = deepcopy(record["visible"])
    order_id = result["order_id"]
    denied = deny_foreign_resource(state, state.orders[order_id]["customer_id"], "order", order_id)
    if denied: return denied
    result.update(status=record["truth"], success=record["truth"] == "completed",
                  completed_amount=record["committed_amount"])
    result.pop("error", None)
    record["visible"] = deepcopy(result)
    state.log_event("action_result", deepcopy(result))
    return result


def render_action_status(events):
    results = {}
    for event in events:
        if event["event_type"] == "action_result":
            result = event["details"]
            results[result["request_id"]] = result
    sentences = []
    for result in results.values():
        status = result["status"]
        description = "completed" if status == "completed" else {
            "accepted": "accepted but not completed", "pending": "pending, not fully completed",
            "failed": "failed; no completion confirmed", "unknown": "unknown; completion is not confirmed"}[status]
        sentences.append(f"Refund request {result['request_id']} for order {result['order_id']}, "
                         f"amount ${result['amount']:g}: {description}. "
                         f"Confirmed completed amount: ${result['completed_amount']:g}.")
    return " ".join(sentences)
