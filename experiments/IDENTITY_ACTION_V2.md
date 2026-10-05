# Identity and action outcome coverage, version 2

`identity_action_v2.json` is a new scenario corpus, separate from frozen
`final_v1.json`. It was authored after the failure analysis and is a development
verification corpus, not evidence of an untouched pre-fix holdout.

Run validation without API calls:

    .venv-review/Scripts/python.exe experiments/identity_action_eval.py --dry-run

Run a small targeted live check:

    .venv-review/Scripts/python.exe experiments/identity_action_eval.py --limit 2

Use `--output experiments/runs/targeted-identity-action-TIMESTAMP` to resume the
same contract. Completed baseline/protected sides, including errors, are retained
independently. Changing corpus, source or model configuration rejects resume.
No application storage module is imported. Pricing remains null.

Scenario state is supplied by the application/test harness, never extracted
from user text or model decisions. The API scenario endpoint is explicitly a
controlled sandbox fixture interface, not an authentication/verification service.
Verification evidence cannot be created through an agent tool. Production
integration would require a trusted verifier to supply session-scoped evidence.

Normal sandbox mutation checks identity and customer ownership. Identity replay
alone includes an explicitly labeled legacy counterfactual baseline that bypasses
the identity gate, while retaining ownership enforcement. This is not the current
application baseline and must not be presented as one. Action replay preserves
the same provider faults and changes only final claim handling.

Refund request identities are deterministic. Order/amount pairs identify one
logical action within a run; repeated identical calls return the same result.
Distinct same-amount refunds within one run require a future explicit request-ID
tool contract. Accepted/pending fixtures do not autonomously settle. Partial
completion exposes the committed portion. Timeout-after-commit requires a status
lookup before completion may be confirmed.

Protected refund responses render canonical current receipts and retain the
original model response and detected unsupported claims in forensic events.
This deliberately prioritizes grounded financial status over preserving unrelated
free-form prose. The independent English rule evaluator has linguistic limits;
canonical protection does not depend on comprehensive regex detection. Grounded
refund status does not establish grounding of email/address claims.

Mitigation is verified only after an intended baseline failure reproduces,
both executions complete, and protected execution has no violations or duplicate
financial mutation and satisfies the scenario utility expectation. Safe baselines
produce a null mitigation result. Positive controls test actual verified address
mutation and truthful completed refund reporting.
