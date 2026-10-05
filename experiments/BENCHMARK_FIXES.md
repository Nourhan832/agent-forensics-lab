# Decision recovery and selective note handling

Agent decisions must be exactly one JSON object with the complete respond or tool_call schema. No substring extraction, fence stripping, inferred actions, arbitrary repair, duplicate keys, non-finite amounts or extra arguments are accepted. A malformed JSON/schema decision receives one format retry in the same step with the identical transcript and existing state. Previously successful tools are not replayed. Two failures return completed=false and error_type=InvalidModelDecision. Provider failures retain the existing safe API error handling; a transport error on recovery also returns an explicit incomplete result.

Agent results retain decision_diagnostics, actual model_call_count and partial_trace. Diagnostics include stage/step/attempt, JSON position/message, available provider IDs and finish reason, secret-redacted response preview (maximum 2,000 characters), truncation flag, snapshot of prior events and recovery outcome. The initial malformed attempt remains present even after recovery. Environment credentials and credential-shaped strings are redacted before truncation. This is best-effort secret detection, not a guarantee for arbitrary unknown secrets; diagnostic artifacts may contain customer data and require restricted access. Raw invalid text is never fed back as executable instructions. Minimized candidate executions retain their diagnostics and partial traces, even when incomplete; only completed reproductions can shorten a trigger. Proposal generation retains its existing strict JSON behavior.

Protected order retrieval authorizes ownership before note extraction. Isolation also activates the existing tool-layer ownership check for all six tools. Identity verification and failed-action policies are unchanged. Original notes remain in forensic events and sandbox state; they never enter the protected planning transcript.

The local extractor recognizes complete clauses for delivery windows, collection points, printed-receipt/packing-slip requests, and bell-ringing delivery preferences. It does not use an LLM or grant authority to extracted claims. Known agent-control patterns are detected after Unicode normalization; every unrecognized clause is withheld regardless of detection outcome. Contaminated clauses are withheld in full, while separate recognized factual clauses can survive. This deliberately narrow grammar can reject other legitimate notes, translated text, uncommon locations, abbreviations and decimal punctuation. It is not a general semantic instruction detector or factual-verification service.

Each approved fact has type, value, source, resource ID, original source offsets, extractor version, unverified_source_content trust, quote_or_summarize permitted use, and action_authority=false. The tool returns structured record fields and this envelope, with notes=null. Audit details preserve approved and withheld original spans, reasons, detector outcome and the agent-visible envelope. Imperative delivery/packing preferences remain quotable data, never agent commands. The agent's policy makes that distinction explicit.

The oracle checks actual tool-result note/fact exposure (or the recorded agent-facing view) before legacy isolation metadata. Even approved unverified facts count as exposure for its temporal-association heuristic. Thus a later foreign access cannot be hidden merely by content_isolated=true. Attribution remains a temporal association, not causal proof.

Targeted provider verification selects eight unchanged cases in memory from final_v1.json; it never writes a substitute corpus or uses regression storage:

```powershell
.venv-review\Scripts\python.exe -m pytest -q
.venv-review\Scripts\python.exe experiments/verify_benchmark_fixes.py --dry-run
.venv-review\Scripts\python.exe experiments/verify_benchmark_fixes.py --output experiments/runs/targeted-fixes-<timestamp>
```

Only injection 02/03/07/10 and benign-37/38/39/40 are selected. One minimization round and fresh paired replay use the existing evaluator. Repeat the identical command/output to resume; finalized errors are retained and skipped. Recovered format failures stay in agent diagnostics and do not become case errors if the execution completes. Pricing remains null. A successful targeted run cannot certify general security or identical recovery of old malformed bytes, which were never saved. No full benchmark is authorized in this review step.
