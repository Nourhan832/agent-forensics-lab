# Review change inventory

Each intentional submission-source change is listed below. `.env`, the working/backup databases and historical experiment result files were not edited. The ignored `.venv-review` contains the review environment and a disposable UI database; these local verification artifacts are not submission source.

| File | Reason |
|---|---|
| `.dockerignore` | Exclude secrets and local data from image build context. |
| `.env.example` | Document server-only provider settings without credentials. |
| `.github/workflows/checks.yml` | Define automated assertions, syntax and artifact checks. |
| `.gitignore` | Exclude credentials, local databases, virtualenvs and caches. |
| `AGENT_FORENSICS_PLAN_REVISED.md` | Mark the historical plan as aspirational rather than implemented claims. |
| `Dockerfile` | Prepare non-root same-origin app packaging with persistent SQLite. |
| `LICENSE` | Add the requested MIT open-source license. |
| `README.md` | Document setup, actual capabilities, architecture, limitations and deployment. |
| `backend/app/agents/attacker.py` | Validate model-generated attack category and text fields. |
| `backend/app/agents/runner.py` | Validate model decisions; record completion, rejected outcomes and actual tool arguments/results. |
| `backend/app/agents/target_agent.py` | Remove duplicate policy heading. |
| `backend/app/api/main.py` | Validate inputs and evidence-bound saves; add expected-class/completion checks, reruns/reports, safe errors, readiness, workflow admission and static serving. |
| `backend/app/evaluation/oracle.py` | Exclude isolated content from exposure and check ownership across instrumented tools. |
| `backend/app/evaluation/response_rules.py` | Reference each failed refund event correctly. |
| `backend/app/forensics/fingerprint.py` | Add canonical stable context identifiers and resource fallbacks. |
| `backend/app/forensics/localizer.py` | Validate event indexes before localization. |
| `backend/app/forensics/minimizer.py` | Enforce shortening and resource ID preservation; recognize action verbs and evaluate complete runs. |
| `backend/app/forensics/replay.py` | Expose the replay-adapter protocol and reusable fresh customer-support adapter; evaluate full runs. |
| `backend/app/forensics/run.py` | Sanitize minimization errors instead of exposing provider text. |
| `backend/app/integrations/nebius_client.py` | Fix import and guard the explicit provider smoke check. |
| `backend/app/integrations/nemotron.py` | Make configuration/client lazy; bound requests and return safe metadata. |
| `backend/app/sandbox/state.py` | Add version/run/sequence/timestamp trace metadata. |
| `backend/app/sandbox/tools.py` | Enforce ownership across tools and audit actor/owner evidence; reject nonfinite or invalid refunds. |
| `backend/app/storage/regressions.py` | Close connections; serialize duplicate saves; support configurable database and durable replay evidence. |
| `cleanup_regressions.py` | Make maintenance import-safe, dry-run by default, and use a unique backup. |
| `docs/ADAPTERS.md` | Explain implemented replay/event/fingerprint boundaries and honest generalization requirements. |
| `docs/CHANGELOG_REVIEW.md` | Inventory every intentionally changed or created submission file. |
| `docs/JUDGE_REVIEW.md` | Record evidence-based before/after scores, ranked gaps, fixes, tests and verdict. |
| `docs/SUBMISSION.md` | Provide a short honest demo sequence and publication/feedback checklist. |
| `docs/ui-rerun-proof.png` | Capture the real browser saved-case rerun PASS in the disposable database. |
| `experiments/benchmark.py` | Add bounded timestamped live experiments with timings, configuration, errors and retained evidence. |
| `experiments/live_smoke.py` | Provide opt-in live route checks on a disposable copy and confirm working database integrity. |
| `experiments/run_experiment.py` | Guard the legacy live experiment and preserve historical files by writing a new timestamped directory. |
| `experiments/run_false_claim_experiment.py` | Guard the legacy live experiment and preserve historical files by writing a new timestamped directory. |
| `experiments/run_identity_experiment.py` | Guard the legacy live experiment and preserve historical files by writing a new timestamped directory. |
| `experiments/summarize_results.py` | Audit CSV/full-JSON evidence and calculate qualified illustrative intervals without model calls. |
| `frontend/app.js` | Use same-origin requests, server evidence IDs and stored-case reruns; fix progress, action gating, error/failed states, navigation and export. |
| `frontend/index.html` | Use served assets and clarify scope, attribution, benchmark denominators and actual-evidence export. |
| `pytest.ini` | Collect isolated assertions separately from manual live checks. |
| `requirements-dev.txt` | Define explicit test dependencies. |
| `requirements-lock.txt` | Capture the complete tested Python 3.12 environment. |
| `requirements.txt` | Pin reviewed direct dependencies. |
| `test_agent_runner.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_agent_split_refund.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_attack_batch.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_attacker.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_cross_customer_access.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_cross_customer_batch.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_failure_fingerprint.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_false_action_claim.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_false_claim_attacker.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_false_claim_forensics.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_forensics_run.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_identity_attacker.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_identity_forensics.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_indirect_attacker.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_indirect_forensics.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_indirect_injection.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_injection_guardrail.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_live_minimization.py` | Guard the existing manual check against import-time model calls or writes. Fix its obsolete result key. |
| `test_minimizer.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_multi_category_batch.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_policy_behavior.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_primary_finding.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_regression_storage.py` | Guard the existing manual check against import-time model calls or writes. Use a temporary database. |
| `test_replay.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_sandbox.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_split_refund.py` | Guard the existing manual check against import-time model calls or writes. |
| `test_target_agent.py` | Guard the existing manual check against import-time model calls or writes. |
| `tests/__init__.py` | Make test helpers importable. |
| `tests/conftest.py` | Block credential loading and live network calls; provide disposable storage/client fixtures. |
| `tests/test_api_storage.py` | Assert replay/save/rerun/report, forgery rejection, duplicate concurrency, safe errors and copy-only migration. |
| `tests/test_assets_and_results.py` | Assert DOM IDs, JS syntax, artifact counts, safe imports, Git exclusions and all investigation categories. |
| `tests/test_forensic_loop.py` | Assert evidence, localization, fingerprints, minimization, tool policies, completion and adapter behavior. |

The review did not publish, push or deploy externally. Docker and GitHub workflow files are prepared configurations; their remote execution is unverified.
