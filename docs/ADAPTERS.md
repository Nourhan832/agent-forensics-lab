# Framework boundaries and the first demo adapter

The customer-support environment is the only implemented domain adapter. Two guardrail configurations are available. There is no LangChain, browser-agent, MCP-agent, or arbitrary production-agent connector in this repository.

## Replay interface used by the code

`backend/app/forensics/replay.py` declares the structural `ReplayAdapter` protocol. `replay_with_adapter` calls `execute(message, protected=False)` and `execute(message, protected=True)`. `CustomerSupportReplayAdapter` creates fresh sandbox state, invokes `run_agent`, evaluates the trace with the customer-support oracle, and returns this shape:

```python
{
    "agent_result": {"final_response": str, "steps": int, "completed": bool},
    "events": list[dict],
    "violations": list[dict],
    "failed": bool,
}
```

A new environment must implement fresh state/reset semantics, its agent runner, tool instrumentation, protected configuration, and a trusted evaluator. Registering a new category also requires mapping the expected failure class and UI behavior. The protocol makes the seam explicit; it is not an SDK with automatic interoperability. A synthetic test exercises the structural seam without claiming a second real adapter exists.

## Version 1 trace contract

`SandboxState.log_event` emits ordered events. Timestamps describe recording time, not model latency. Sequences are zero-based within a UUID run. Domain `details` are authored by trusted tool code, not the model. The runner adds tool arguments and actual results to events, including rejected tool calls that previously produced no event.

```json
{
  "schema_version": "1.0",
  "run_id": "UUID",
  "sequence": 0,
  "recorded_at": "UTC ISO-8601",
  "event_type": "lookup_order",
  "details": {
    "order_id": "O2001",
    "found": true,
    "authenticated_customer_id": "C001",
    "order_customer_id": "C002",
    "content_isolated": false
  },
  "tool_name": "lookup_order",
  "arguments": {"order_id": "O2001"},
  "result": {"success": true}
}
```

Direct sandbox calls outside `run_agent` emit the base event without the runner additions. Legacy artifacts have only `event_type` and `details`; the oracle still accepts them. This contract currently uses dictionaries rather than a validated universal event registry. It records tool decisions and outcomes, not hidden model reasoning, token usage or a complete chat transcript. It is not an immutable or signed audit log.

The domain oracle uses ownership, cumulative refund amount, supervisor approval and identity evidence. `evaluate_events` adds cross-customer findings for instrumented customer tools; `evaluate_run` adds the false-refund response heuristic. A blocked attempt records `access_denied` and does not constitute successful access. Unknown event types are not interpreted as safe by a generic policy engine; they simply have no configured rules. Adapter authors must supply rule coverage and integrity checks before drawing safety conclusions.

Injection attribution requires untrusted notes actually exposed to the model and a later foreign-order lookup. Removing notes from the model input leaves the original note in forensic evidence, with `content_isolated=True`; this does not count as exposure. Temporal succession is evidence of the tested scenario, not proof that the note caused the action. No clean-note counterfactual is executed.

## Fingerprints and evidence

`create_failure_fingerprint` computes SHA-256 from a canonical JSON identity containing failure class, critical tool/event, authenticated actor, resource owner, target resource and injection source. Prompt wording, generated goals, timestamps and event positions are excluded. These IDs group equivalent failure contexts; they are not a proof of cause or a cryptographic seal on the complete trace. Customer/refund resource fallbacks are included where evidence provides them.

Regression deduplication uses a different identity: category, failure class, trimmed trigger and guardrail. Multiple wording variants may share a failure fingerprint while remaining separate regression triggers. Reports retain evidence; an original discovered prompt is user-supplied metadata unless exported with the actual investigation.

## Generalization work still required

1. Implement and demonstrate a second real environment, ideally a file/tool or account-access agent.
2. Validate external event provenance and completeness; add a policy registry per domain.
3. Preserve environment version, configuration, model ID and reset recipe in durable case schemas.
4. Compare harmful-action detection and legitimate task utility before and after mitigation.
5. Add agent SDK hooks, redaction, durable jobs, authentication and tenancy for production use.

These are future work, not capabilities implied by the protocol.
