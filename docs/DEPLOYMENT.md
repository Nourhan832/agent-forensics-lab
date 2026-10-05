# Production deployment readiness

**READY TO DEPLOY as a bounded public sandbox demo**, using the single-worker, HTTPS-ingress and persistent-volume configuration below. No public deployment was performed.

## Startup

From the project root, with Python 3.12 and the pinned dependencies installed:

```sh
python -m backend.app.api.serve
```

This entry point binds `0.0.0.0`, reads `PORT` (8000 by default), runs exactly one worker and never enables reload/debug. Equivalent Linux command when proxy headers are not needed:

```sh
python -m uvicorn backend.app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-proxy-headers
```

Inject secrets through the hosting platform, rather than including an `.env` in the image. `/health` checks liveness; `/ready` checks storage and required model configuration. Readiness does not verify provider connectivity/quota: the live acceptance below checked connectivity separately.

## Production configuration

| Variable | Requirement / default |
|---|---|
| `NEBIUS_API_KEY` | Required server secret; never supply to the browser. |
| `NEBIUS_BASE_URL` | Required provider endpoint; intended value `https://api.tokenfactory.nebius.com/v1/`. |
| `NEBIUS_MODEL` | Required model ID; tested `nvidia/nemotron-3-super-120b-a12b`. |
| `AFL_DATABASE_PATH` | Required deployment setting: absolute writable path on persistent storage, e.g. `/data/agent_forensics.db`. Local default is the project-root DB; do not rely on an ephemeral application filesystem in deployment. |
| `PORT` | Platform-assigned port, otherwise 8000. |
| `NEBIUS_TIMEOUT_SECONDS` | Provider request timeout; default/recommended 45. |
| `NEBIUS_MAX_RETRIES` | SDK retries; default/recommended 1, allowed 0–3. |
| `AFL_CORS_ORIGINS` | Blank for same-origin. For a separate frontend, list exact origins separated by commas; no wildcard or embedded credentials. |
| `AFL_BUDGET_DATABASE_PATH` | Optional; otherwise `afl_public_budget.sqlite3` beside the regression DB. Must also be on persistent storage. |
| `AFL_MAX_CONCURRENT_REQUESTS` | Default/recommended 32 admitted HTTP requests. |
| `AFL_MAX_CONCURRENT_WORKFLOWS` | Default/recommended 1 active investigation/replay per process. |
| `AFL_RATE_LIMIT_REQUESTS` | Default/recommended 6 API POST attempts per peer per window, including save/rerun. |
| `AFL_RATE_LIMIT_WINDOW_SECONDS` | Default/recommended 60 seconds. |
| `AFL_MAX_REQUEST_BYTES` | Default/recommended 32768 bytes, including streamed bodies. Replay message schema additionally caps messages at 8000 characters. |
| `AFL_MAX_MODEL_CALLS_PER_WORKFLOW` | Default/recommended 128 logical model calls across the entire HTTP workflow, including minimization and format recovery. Each agent execution retains the unchanged hard limit of 8 decision steps and one bounded format retry. |
| `AFL_DAILY_MODEL_REQUEST_LIMIT` | Default/recommended 500 reserved provider request-attempt slots per UTC day. With one SDK retry, each logical model call reserves 2 slots, so at most 250 logical calls/day are admitted. Failed calls and unused retry reservations remain charged to the allowance. These are conservative admission slots, not actual retry counts or monetary estimates. |
| `AFL_MODEL_MAX_OUTPUT_TOKENS` | Optional public-HTTP output cap. Recommended and acceptance-tested value 4096; unset preserves the existing provider default. Does not apply to benchmark/CLI calls. |
| `AFL_TRUSTED_PROXY_IPS` | Optional exact trusted ingress IPs/CIDRs. Leave blank to ignore caller-controlled forwarded headers. No wildcard. If blank behind a proxy, users share that proxy's rate bucket. |

Python's `PYTHONDONTWRITEBYTECODE`/`PYTHONUNBUFFERED` are set in the image. `PYTHON_DOTENV_DISABLED=1` may be used to disable dotenv loading when the platform injects all configuration; it is not required. `window.AFL_API_BASE` is an optional frontend configuration override, not an environment variable consumed by the server. Set it before `app.js` for a separately hosted API and allow the frontend's exact origin through CORS.

No pricing-based budget is configured or inferred. The HTTP daily request allowance prevents unrestricted model usage, while preserving benchmark/CLI behavior. Apply provider-account usage controls as an additional operational boundary.

## Persistence and ingress

Mount one writable persistent volume at `/data` (or an equivalent configured directory). Both the regression database and budget sidecar must survive restarts/redeploys. Startup migrations and budget initialization are idempotent; neither resets existing evidence or allowance. The image runs as UID 10001: ensure that bind-mounted disk ownership permits this UID to write. Named Docker volumes inherit the image's `/data` ownership on first initialization.

Use one worker and one application replica. HTTP/per-peer/workflow counters are process-local; the daily allowance is atomic SQLite state. Multi-replica operation is outside this deployment recommendation. SQLite is unsuitable for an ephemeral serverless filesystem. Never mount the developer's working database into a public instance.

Put HTTPS termination, connection/body limits and request timeouts at the hosting ingress. Allow sufficient request duration for multi-call investigations; calls are synchronous and there is no background job queue. If proxy headers are needed, configure only known trusted ingress addresses. CORS is not authentication. The public app intentionally exposes fictional sandbox regression evidence; it has no login/tenant boundary and must not be connected to real customer or emergency systems.

## Docker

```sh
docker build -t agent-forensics-lab .
docker volume create afl-data
docker run --rm -p 8000:8000 --env-file .env -e AFL_MODEL_MAX_OUTPUT_TOKENS=4096 -v afl-data:/data agent-forensics-lab
```

The Docker context excludes credentials, local databases, caches, acceptance artifacts and development output-path pointers. The image copies backend/frontend source, the dependency lock and exactly the frozen emergency corpus and USGS snapshot required at runtime. Credentials are not copied or baked into image layers. The startup and healthcheck both honor `PORT`.

Docker is unavailable in the audit environment. Dockerfile/COPY requirements, non-root configuration, ignore patterns and startup were statically checked; an actual image build/container run has **not** been verified. Perform the build on the target host/CI before publishing the instance.

## Acceptance evidence — 5 October 2026

- **404 automated tests passed**; 21 deployment tests added to the previous 383 tests.
- Python compile check and JavaScript syntax check passed.
- `pip check` passed; all 30 locked distributions match the installed versions.
- Production startup without reload served `/health`, `/ready`, `/`, static assets and both domain category APIs with HTTP 200.
- One live customer-support investigation and one frozen emergency investigation completed.
- Emergency paired replay reproduced the intended failure, completed both executions, preserved protected utility, observed zero protected violations and VERIFIED mitigation.
- A verified emergency regression was saved and read in isolated acceptance storage; its live rerun completed with VERIFIED mitigation.
- An actual overlapping live workflow received 429 without another provider workflow starting.
- Restart preserved all regression fields, full replay evidence and 38 reserved request-attempt slots (19 logical model calls with one retry allowance each). This is not a claim that 38 network attempts occurred.
- Live error checks: invalid category 400, malformed request 422, missing regression 404, rate rejection 429. Automated provider-timeout check returned a generic 502; budget exhaustion and concurrency rejections were also tested.
- Browser same-origin operation, domain switching, simulated-emergency label and frozen benchmark evidence verified; no captured warning/error logs. Optional API-origin override verified independently in the existing JavaScript expression.
- Publishable source scan: no configured credentials or credential-shaped literals detected. Three existing absolute development output pointers were excluded through ignore rules, without edits. `.env` remains ignored and the example contains no credential values. Git metadata/history is absent, so tracked/history secret scanning was unavailable.
- **937 protected files unchanged**, covering UI files, forensic/policy/domain logic, experiment code, frozen corpora, historical artifacts, credential files and existing databases.
- Emergency operations, alerts, customer email and financial/account actions remain in-memory simulation. Tool schemas expose no shell/file/environment/arbitrary-URL capabilities; only the server-configured provider receives network requests. No model policy/system prompt was changed.

Local raw records and verification are under `artifacts/deployment-audit-20261005/`, which is excluded from publication. The audit used new isolated database files, not the working database. No benchmark was rerun or result rewritten.

## Exact deployment-readiness changes

1. `backend/app/api/main.py`: configurable workflow admission, public limits, idempotent budget initialization, minimal CORS and non-echoing validation errors.
2. `backend/app/api/deployment.py` (new): request concurrency/rate/body limits and durable conservative provider-request allowance.
3. `backend/app/api/serve.py` (new): portable single-worker production startup honoring PORT and trusted proxy configuration.
4. `backend/app/integrations/nemotron.py`: configurable SDK retries; public-context request reservations and optional output cap. Existing defaults and non-HTTP benchmark behavior remain intact.
5. `Dockerfile`: include required frozen emergency runtime files and use the production entry point/PORT-aware healthcheck.
6. `.dockerignore`: exclude private acceptance data, sidecar databases, development pointers and credential-file formats.
7. `.gitignore`: exclude development output-path pointers; existing historical artifacts remain unchanged.
8. `.env.example`: document server-only deployment settings and placeholders.
9. `README.md`: correct deployment packaging/rate-budget descriptions and link this guide.
10. `tests/test_deployment_readiness.py` (new): 21 deployment control, error, persistence and packaging tests.
11. `docs/DEPLOYMENT.md` (new): this configuration, acceptance and limitation report.

Remaining non-blocking limitations: Docker image execution and a real hosting platform/HTTPS ingress have not been tested; Git history is unavailable; there is no authentication, tenant isolation, job queue or automated evidence retention; rate/workflow controls assume the documented single-worker deployment. Readiness is configuration/storage-only. Replay remains model-dependent and some evaluators are rule-based. Emergency actions remain simulated and the earthquake feed is frozen, not live.

## Render Blueprint

`render.yaml` defines a native Python web service using Python 3.12.14. Build with `python -m pip install -r requirements-lock.txt`; start with `python -m backend.app.api.serve`. Render supplies `PORT`; `/health` is the platform health check. Keep one worker and `numInstances: 1`.

The Blueprint uses the paid Starter plan because [Render persistent disks require a paid service](https://render.com/docs/disks). A 1 GB disk mounts at `/var/data`:

- `AFL_DATABASE_PATH=/var/data/agent_forensics.db`
- `AFL_BUDGET_DATABASE_PATH=/var/data/afl_public_budget.sqlite3`

The explicit demo settings are `AFL_MAX_CONCURRENT_WORKFLOWS=1`, `AFL_RATE_LIMIT_REQUESTS=6`, `AFL_RATE_LIMIT_WINDOW_SECONDS=60`, `AFL_DAILY_MODEL_REQUEST_LIMIT=500` and `AFL_MODEL_MAX_OUTPUT_TOKENS=4096`. Other existing bounds are also listed in the Blueprint. `PYTHON_VERSION=3.12.14` follows [Render's version-pinning mechanism](https://render.com/docs/python-version).

`NEBIUS_API_KEY` has only a `sync: false` placeholder. Supply the actual value through authenticated Render secret settings. `NEBIUS_BASE_URL` and `NEBIUS_MODEL` are non-secret configured values. Never upload the local working database or `.env`. A new public instance creates its own database through the existing startup migration path.

Same-origin hosting uses blank `AFL_CORS_ORIGINS`. `AFL_TRUSTED_PROXY_IPS` remains blank until exact trusted ingress addresses are known; forwarded headers are not accepted automatically. Clients behind a common Render proxy may therefore share a rate bucket. Do not substitute a wildcard to avoid that limitation.

The disk is available at runtime, not during build/pre-deploy. Disk-backed redeploys have a brief interruption; persistence must be verified after one restart/redeploy. A Blueprint deployment is not complete until the private GitHub repository is accessible to Render and the secret is configured.

### Public acceptance after deployment

Check `/`, `/health`, `/ready`, `/assets/app.js` and `/assets/styles.css`; verify both domain selectors and category cards. Complete one customer investigation, one emergency investigation, a protected replay, a verified regression save and a rerun using the new service database. Check 400/422/404 and 429 responses without tracebacks, paths or credentials. Space checks across the configured six-POST/minute allowance; do not relax the limit for testing.

Record the saved regression ID and its full report, restart/redeploy once, then compare the stored report and request-budget state. `/ready` only checks storage/configuration; a completed model workflow is required to establish provider access. Preserve all failed acceptance results and keep private raw evidence outside the published repository.

## Fly.io single-Machine deployment

`fly.toml` deploys the unchanged Dockerfile to `agent-forensics-lab` in Frankfurt (`fra`): one shared CPU, 512 MB RAM, port 8000, forced HTTPS, and one encrypted 1 GB `afl_data` volume mounted at `/data`. The existing non-root UID 10001 owns the mounted path. Both SQLite files reside on that volume; do not add replicas or clone this Machine.

Import only `NEBIUS_API_KEY` through Fly secrets, never through the TOML file or image. All non-secret public limits and provider configuration are in `fly.toml`. Deploy with `fly deploy --remote-only --ha=false`; the CLI may create a separate temporary remote-builder app/cache, which can be removed after a successful build. Redeploy a retained image with `fly deploy --image <registry.fly.io image reference> --ha=false`. The immediate deployment strategy updates the one Machine with brief downtime, preserving its attached volume.

Autostart is enabled; idle autostop uses `stop`, with zero minimum running Machines. The public demo is https://agent-forensics-lab.fly.dev/. The trial deployment used no payment method. Fly's trial includes up to two VM hours or seven days, whichever expires first, and trial Machines automatically stop after five minutes. It is suitable for testing, not guaranteed uninterrupted judging availability. Adding a card ends the trial and starts usage billing; do not add one automatically.

On 5 October 2026, public root/health/readiness/assets and both domain APIs passed. Live customer and emergency investigations, protected emergency replay, saved-regression rerun, duplicate-save prevention, forced HTTPS, rate limits and safe 400/422/404 responses passed. Both replay and rerun reproduced the baseline failure with zero protected violations and VERIFIED mitigation. Duplicate dispatch counts were zero. SQLite integrity checks were `ok`, both database content digests matched across redeployment, and the full saved report survived stop/start and redeployment. Public autostart after a deliberate stop took approximately eight seconds. Private evidence is in ignored `artifacts/fly-acceptance-20261005/`.

The unchanged floating `python:3.12-slim` image resolved to Python 3.12.15; the deployed image digest, rather than an assumed patch version, records the exact container. Automated tests: 404 passed; JavaScript syntax passed. The frontend served byte-for-byte unchanged files. Local credentials, working databases, frozen corpora and historical artifacts remained unchanged.

The [Fly calculator](https://fly.io/calculator/) quoted $4.26/month for one continuously running Frankfurt shared-CPU 512 MB Machine and $0.15/month for its 1 GB volume (730-hour calculator assumption), excluding outbound traffic, Token Factory inference, stopped-rootfs charges, excess snapshots and any future builder usage. Autostop reduces compute usage; the volume remains billable after the trial. One local volume is not replicated high availability. Retain `render.yaml` as a fallback; the public-demo primary host is Fly, subject to its trial/runtime limits.
