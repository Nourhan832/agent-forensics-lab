# Second domain: simulated emergency incident commander

This is a second tool-using sandbox domain, not a real emergency-service
integration. The operational entities, actors, Zones A/B, approval policies,
resources, dispatches and alerts are entirely simulated. Real earthquake fields
come from three USGS events snapshotted on 2026-10-04:

| Event ID | Magnitude | Region |
|---|---:|---|
| us6000tz1y | 4.7 | 5 km NNE of Korumburra, Australia |
| us6000txpi | 6.6 | 80 km ENE of Tadine, New Caledonia |
| us7000ti1p | 6.5 | 177 km W of Nikolski, Alaska |

Source: [official USGS feed](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson).
The versioned `data/emergency_response/usgs_events_v1.json` preserves source IDs,
URLs, retrieval dates, exact coordinates, depth, timestamps and tsunami flags.
The flag is retained as a flag; this sandbox never promotes it to confirmation
of a tsunami or an evacuation order. Magnitude >=6 is this simulation's
classification threshold, not an official emergency response recommendation.

## Architectural comparison

| Aspect | Customer support | Emergency response |
|---|---|---|
| Tools | Customer/order lookup, refund, address, email, action status | Incident/report/resource lookup, approval request, allocation, public alert, dispatch status, incident report |
| Resource model | Customer-owned orders and profiles | Jurisdiction-scoped teams, real event snapshots, simulated incident/dispatch/alert records |
| Policies | Ownership, refund limit, scoped identity, note isolation, refund grounding | Jurisdiction and role, unit threshold, scoped approval, field-report isolation, event and dispatch grounding |
| Findings | Cross-customer access, injection, identity bypass, false refund claims | Unauthorized dispatch, injection, unsupported incident claims, false dispatch claims |
| Trust boundary | Business data versus free-text notes and model claims | USGS structured facts versus simulated policy state versus external field-report text |

## Shared engine, not a parallel forensic system

The emergency adapter calls `investigate_with_adapter` in the existing forensic
run module. That orchestration uses the existing localization and fingerprint
functions, the existing minimizer with a domain reproducer/identifier pattern,
and the existing `replay_with_adapter` abstraction. It does not copy these
algorithms into the emergency package.

Reused unchanged:

- Existing trace recorder/envelope (`SandboxState.log_event`, called directly).
- Localization (`localize_critical_steps`).
- Paired replay (`replay_with_adapter`) and the customer replay adapter.
- SQLite regression storage, scenario-aware deduplication, replay persistence,
  retrieval and JSON evidence payloads.
- Safe diagnostic redaction, bounded format retry and provider usage capture.

Shared components extended with backward-compatible optional hooks:

- Decision parser: caller-supplied tool schemas and positive integer units.
- Agent runner: domain tool map, system prompt and final claim grounding hook.
- Oracle entry point: domain deterministic evaluator.
- Minimizer: domain identifiers, request verbs and fresh-state reproducer.
- Fingerprint source-resource fallback for non-order injection evidence.
- Core investigation entry point for adapter-driven workflows.

The new core `verification.py` checks the expected failure class specifically,
completed execution, protected safety and utility. Another violation is never
accepted as reproduction of the intended failure.

Customer-specific sandbox tools/state, policies, selective-note implementation,
customer replay implementation and customer corpus were not edited. Optional
shared hooks preserve the original defaults; the full existing test suite remains
part of validation.

## Usage and evidence

    .venv-review/Scripts/python.exe experiments/emergency_verify.py --dry-run
    .venv-review/Scripts/python.exe experiments/emergency_verify.py --limit 7

Only seven selected cases can run live through this bounded runner. No large
benchmark mode exists. Each case uses the shared investigation plus fresh paired
replay; `--minimize-rounds 1` enables one actual core minimization round.
Tests validate minimization offline without incurring provider charges.

The runner writes a new timestamped `experiments/runs/emergency-targeted-*`
directory with model/corpus/snapshot/code provenance, complete evidence JSON,
usage, summary and a disposable `regressions.db`. Completed case records resume
only under the same contract. Expected failures that do not reproduce retain a
null mitigation result, and provider failures remain explicit incomplete traces.
Only verified cases become regressions; all replay evidence remains persisted.

`experiments/snapshot_earthquakes.py` can ingest saved GeoJSON or explicitly fetch
USGS. It never overwrites a snapshot. Normal tests and demos load committed data
and require no USGS network access.

## Limitations

- This demonstrates one substantially different additional domain, not universal
  generalization or a production incident-command system.
- Baselines are explicitly unsafe sandbox counterfactuals; protected execution
  applies deterministic policy enforcement. Actual services are never contacted.
- Field fact extraction is an allowlist. Unknown observations are withheld;
  preserve their original spans for review rather than treating them as true.
- Claim evaluation uses incident/receipt binding and status checks plus English
  phrase rules. It is not complete semantic entailment. Canonical dispatch status
  delivery does not depend on exhaustive phrase detection.
- Scoped supervisor approvals are trusted deterministic fixtures, not a real
  supervisor workflow. Requests without preexisting approval remain pending.
- Same incident/resource/units within one run identify one logical allocation.
  Distinct identical allocations need a future explicit request-ID contract.
- Pending dispatches reserve simulated units but never imply deployment. They do
  not settle autonomously; timeout-after-commit status can reconcile completion.
- Real event metadata and synthetic field reports/policies must remain distinct.
- Temporal report/action association is not proof of injection causality.
- The second domain is available through the adapter and bounded CLI; the existing
  customer dashboard/API has not been relabeled as a multi-domain interface.

## Verification outcome (2026-10-04)

The full configured automated suite passed **225 tests**. Offline tests exercise
all four baseline failures and protected mitigation through actual domain tools
and the shared engine, including minimization, localization, fingerprints and
scenario-preserving regression storage. These are scripted tests, not live model
benchmark results.

Seven selected real-provider cases completed using Nebius Nemotron at temperature
0. Protected utility passed 7/7, including both benign descriptive tasks and the
legitimate authorized dispatch. No protected violations or duplicated dispatches
were observed. No intended baseline failure reproduced under corrected evaluation,
so no live mitigation rate is claimed. The requested live baseline-failure
demonstrations were therefore **not established** by this bounded run.

The first emergency-claim finding was a false positive on hypothetical rejection
of an inaccurate tsunami alert; the initial mixed-report utility check rejected
a valid grammatical paraphrase. Both checks were corrected and tested. Preserved
live traces were reassessed locally without altering prompts/corpus or making more
provider calls. The separate corrected assessment is:

`experiments/runs/emergency-assessment-20261004-225832/assessment.json`

Original live evidence is:

`experiments/runs/emergency-targeted-20261004-225222/`

The isolated original run database retains a regression saved from the initial
false positive. That record is **not verified under corrected evaluation**; the
separate assessment explicitly invalidates that inference without overwriting
raw evidence. It was never saved to the working database.

All 432 preexisting snapshotted historical artifacts, credentials, frozen corpus
and databases remained byte-for-byte unchanged. Customer-specific implementation
files were not edited; six shared core files received optional extension hooks,
and one shared verification module was added. This is architectural integration
evidence, not proof of universal robustness or live attack success.
