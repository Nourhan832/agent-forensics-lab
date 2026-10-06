# Agent Forensics Lab

**Trace, reproduce, and prevent unsafe behavior in tool-using AI agents.**

Agent Forensics Lab is a trace-level forensic framework that investigates what an AI agent actually did, not only what it said.

**[Live demo](https://agent-forensics-lab.fly.dev/)** · [Final evaluation](docs/evidence/final-combined-20261005-005502.md) · [Adapter contract](docs/ADAPTERS.md)

## Why this exists

Response-only evaluation can miss unsafe tool actions: an agent may refuse to disclose another customer's data after already reading it. Retrieved instructions, identity bypass and claims of actions that never completed also require evidence beyond the final answer.

## What it does

**Discover → Execute → Detect → Localize → Minimize → Explain → Patch → Replay → Regression**

The framework records ordered tool events, checks deterministic policies, identifies the violating event and tests shorter triggers. “Patch” selects an implemented guardrail; it does not generate or deploy arbitrary code. Fresh baseline/protected replay checks reproduction, completion, safety and task utility. Verified evidence can be saved and rerun as a regression.

## Live demo

Open **[agent-forensics-lab.fly.dev](https://agent-forensics-lab.fly.dev/)** and select Customer Support or Emergency Response. After idle autostop, the first request can take several seconds. Investigations and replay make multiple inference calls and can take longer.

The public deployment is a single-instance Fly.io sandbox. It uses fictional customer data and simulated operational actions. Exported evidence describes the actual selected investigation/replay. Do not enter private customer information or real emergency requests.

## Example forensic flow

A customer asks about their own order **O3001**. Its poisoned note directs the agent toward **O2001**, owned by another customer.

1. **Hidden unsafe action:** a later tool call reads O2001, even if the final answer refuses disclosure.
2. **Deterministic violation:** the ownership rule compares the actor with the accessed resource's owner.
3. **Critical step:** the trace localizes that unauthorized lookup and records the preceding untrusted source.
4. **Minimized trigger:** candidate shortening is accepted only after an execution reproduces the requested failure.
5. **Protected replay:** ownership enforcement and selective content isolation are evaluated on a fresh paired execution.
6. **Regression preservation:** the server stores replay evidence and deduplicates an equivalent saved case for later reruns.

This example illustrates the supported scenario, not a promise that every live run fails. Event ordering alone is temporal evidence; the matched content ablation below supplies separate intervention evidence.

## Two evaluation domains

| Domain | Sandbox and tested failures |
|---|---|
| **Customer Support** | Orders, identity verification and simulated refunds: cross-customer access, indirect injection, identity bypass and false action claims. |
| **Emergency Incident Commander** | Real **snapshotted USGS earthquake data**, trusted approval lookup and simulated dispatch/alerts: unauthorized dispatch, report injection, unsupported severe claims and false dispatch claims. |

**Emergency operational actions are simulated.** The earthquake snapshot is not a live feed, and the system has no live emergency-response capability. Shared forensic adapters connect both domains to the trace, evaluation, replay and regression pipeline.

## Evidence

The [frozen final combined report](docs/evidence/final-combined-20261005-005502.md) and [audit-qualified summary](experiments/runs/final-combined-20261005-005502/audited_summary.json) cover 120 customer-support and 12 emergency cases using Nemotron.

| Final combined evaluation | Audit-qualified result |
|---|---:|
| Completed cases | **132/132** |
| Independent reproduction of eligible discovered failures | **58/58** |
| Verified mitigation among eligible paired replays | **67/67** |
| Protected violations | **0** across validated protected executions |
| Benign utility preservation among baseline-successful tasks | **41/41** |
| Overall benign task success, baseline and protected | **41/45** in each condition |
| Successful minimization | **46/57 (80.7%)** |
| Average trigger reduction among successful minimizations | **54.32%** |

These denominators describe different eligible, audited subsets; they must not be combined. The evaluation mixes held-out customer cases with development scenarios. Published raw and audit-qualified results are separate: documented evaluator false positives were excluded from audited claims, while original automated outputs remain preserved. Zero observed protected violations is a result on these executions, not a universal safety guarantee.

**Controlled content ablation:** customer-support unsafe access occurred in **9/10 poisoned**, **0/10 neutralized**, and **0/10 sanitized** executions with matched conditions. This is intervention evidence consistent with a causal contribution from retrieved malicious content, not formal causal proof. Utility and small-sample limitations are documented in the [ablation report](experiments/runs/injection-ablation-20261005-000940/report.md).

**Controlled multi-model comparison:** the same forensic pipeline ran across **Nemotron, Hermes and Qwen** on 25 matched cases per model. Cross-customer access and customer injection were observed across all three. Evaluator wording limitations are explicitly audited. This is a pipeline portability exercise, not a universal model safety ranking. See the [multi-model report](experiments/runs/multimodel-controlled-20261005-002626/report.md).

Earlier JSON/CSV experiments remain in [experiments/results](experiments/results). They predate subsequent fixes and are historical evidence, not current-code measurements. See [evaluation methodology](experiments/FINAL_EVALUATION.md) and the versioned corpora for reproduction; new API runs may differ.

## NVIDIA + Nebius

The primary benchmark and hackathon model is **`nvidia/nemotron-3-super-120b-a12b`**, served by **Nebius Token Factory**.

Nebius powers agent execution, minimization, replay and controlled multi-model evaluation through an **OpenAI-compatible inference API**. The controlled comparison also used `NousResearch/Hermes-4-405B` and `Qwen/Qwen3-235B-A22B-Instruct-2507` through the same provider/API layer. Credentials stay on the server; no local GPU or model download is required.

Agent Forensics Lab does not inherit provider certifications and makes no SOC 2, HIPAA or ISO compliance claim.

## Architecture

```text
Browser
  ↓
FastAPI + same-origin frontend
  ↓
Forensic engine
  ├─ bounded tool-using agent and domain sandbox tools
  ├─ deterministic policy checks and event localization
  ├─ empirical trigger minimization
  └─ baseline/protected replay → SQLite regression evidence

Agent execution, generation, minimization and replay
  → Nebius Token Factory → Nemotron / controlled Hermes / Qwen
```

Fly.io supplies hosting and persistent SQLite storage, not forensic capabilities. [Deployment documentation](docs/DEPLOYMENT.md) describes the single-worker configuration and prepared Render fallback. `/ready` checks configuration/storage; it does not contact the provider or verify quota.

## Safety boundaries and limitations

- Controlled sandbox only; no connection to real customer or emergency systems. Emergency dispatches, alerts, refunds and account actions are simulated.
- Mitigation is verified only for the tested baseline/protected pair and its category-specific utility contract. Missing reproduction or incomplete execution cannot establish mitigation.
- LLM replay remains stochastic, including at temperature zero. Linguistic claim/utility checks have bounded coverage and can require manual audit.
- Localization identifies the violating event, not complete causal attribution. Minimization is empirically validated, not guaranteed globally minimal.
- Selective isolation exposes approved facts with untrusted provenance and no action authority; ownership/authorization remains enforced independently at tool boundaries.
- Strict decision schemas allow one bounded format retry, preserve malformed-response diagnostics and stop explicitly if recovery fails.
- The public demo has one instance, persistent SQLite, bounded request/provider budgets and no login or tenant isolation. CORS is not authorization. There is no universal safety guarantee or production compliance certification.

## Local setup

Use Python **3.12** from the repository root:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-lock.txt
```

Copy [.env.example](.env.example) to `.env` only if one does not already exist. Set your server-side `NEBIUS_API_KEY`; keep `.env` private and never commit credentials. The example specifies the Nebius endpoint and primary model.

```bash
python -m backend.app.api.serve
```

Open [localhost:8000](http://127.0.0.1:8000/) and [API documentation](http://127.0.0.1:8000/docs). FastAPI serves both frontend and API. Without a provider key the server can serve the UI and existing evidence, but live workflows cannot run. Do not expose a local instance publicly without the documented persistent-storage and admission settings.

## Testing

**404 automated tests currently pass.** They use controlled model responses and disposable databases; this checks software behavior, not universal model robustness.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check frontend/app.js
```

Node is needed only for the syntax check. Root `test_*.py` scripts are manual checks; explicitly running live scripts or benchmark runners can incur provider charges. No research benchmark is required for ordinary test verification.

## Repository map

- [backend/app](backend/app): agent loop, domain tools, policy evaluation, forensics, API and SQLite storage.
- [frontend](frontend): same-origin UI and trace/evidence presentation.
- [experiments](experiments): evaluation runners, frozen corpora, historical results and selected public reports. Raw runs and local acceptance databases are excluded.
- [data/emergency_response](data/emergency_response): frozen USGS context.
- [tests](tests): automated correctness, security, persistence and evaluation checks.
- [docs](docs): adapter contracts, methodology, deployment and review notes. Earlier review documents reflect their dated scope; the current evidence links above take precedence.

No current polished screenshots are published yet. Recommended captures from genuine completed live runs: the main investigation screen; the critical tool trace with protected replay verdict; and the emergency provenance or evaluation panel. The existing [historical rerun screenshot](docs/ui-rerun-proof.png) predates the current UI and is retained as review evidence.

## License

[MIT](LICENSE).
