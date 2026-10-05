from contextlib import asynccontextmanager, contextmanager
import logging
import os
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from openai import OpenAIError

from backend.app.forensics.run import run_forensics, PRIMARY_FAILURE_BY_CATEGORY
from backend.app.forensics.replay import replay_cross_customer_failure, replay_indirect_injection_failure, replay_identity_failure, replay_false_action_failure
from backend.app.integrations.nemotron import model_configuration, provider_retries
from backend.app.api.deployment import (Settings, cors_origins, DailyAllowance, budget_path, PublicAdmissionMiddleware, PublicLimitExceeded, public_workflow_budget)
from backend.app.storage.regressions import (
    initialize_regression_storage, save_regression_case, list_regression_cases,
    get_regression_case, save_replay_run, get_replay_run, list_replay_runs, get_connection,
)

from backend.app.api import emergency

CATEGORIES = {
    "cross_customer_data_access": ("Cross-Customer Access", "critical", "Tests access to another customer's resources."),
    "indirect_prompt_injection": ("Indirect Prompt Injection", "critical", "Tests unsafe actions following untrusted retrieval."),
    "false_action_claim": ("False Action Claim", "high", "Checks refund completion claims against current action results."),
    "identity_bypass": ("Identity Bypass", "high", "Tests account changes without verified identity."),
}
REPLAY_ADAPTERS = {
    "identity_bypass": (replay_identity_failure, "identity_verification"),
    "false_action_claim": (replay_false_action_failure, "action_grounding"),
    "cross_customer_data_access": (replay_cross_customer_failure, "access_control"),
    "indirect_prompt_injection": (replay_indirect_injection_failure, "content_isolation"),
}
deployment_settings = Settings.from_environment()
workflow_slots = BoundedSemaphore(deployment_settings.concurrent_workflows)


@asynccontextmanager
async def lifespan(app):
    initialize_regression_storage()
    DailyAllowance(budget_path()).initialize()
    yield


app = FastAPI(title="Agent Forensics Lab", version="0.2.0", lifespan=lifespan,
              description="Controlled sandbox: trace evidence, deterministic rules, LLM-guided minimization and exact-case stochastic replay.")
app.add_middleware(PublicAdmissionMiddleware, settings=deployment_settings)
app.add_middleware(CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])




class ReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=8000)
    scenario: dict | None = None


class RegressionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category: str = Field(min_length=1, max_length=80)
    failure_class: str = Field(min_length=1, max_length=80)
    original_trigger: str | None = Field(default=None, max_length=8000)
    minimal_trigger: str = Field(min_length=1, max_length=8000)
    guardrail: str = Field(min_length=1, max_length=80)
    status: str = "verified"
    mitigation_verified: bool
    before_violations: list[str] = Field(max_length=50)
    after_violations: list[str] = Field(max_length=50)
    replay_id: str = Field(min_length=1, max_length=40)


@contextmanager
def model_workflow():
    if not model_configuration()["configured"]:
        raise HTTPException(503, "Model configuration is incomplete; see .env.example.")
    if not workflow_slots.acquire(blocking=False):
        raise HTTPException(429, "Another model workflow is running; retry after it completes.", headers={"Retry-After": "5"})
    try:
        with public_workflow_budget(deployment_settings, provider_retries()) as budget:
            try:
                yield
            finally:
                # Adapters preserve incomplete evidence but may catch provider exceptions.
                # A public limit rejection must still reach HTTP callers as an explicit 429.
                if budget.rejection is not None:
                    raise budget.rejection
    except PublicLimitExceeded as error:
        raise HTTPException(429, str(error), headers={"Retry-After": str(error.retry_after)}) from None
    except OpenAIError as error:
        logging.getLogger(__name__).warning("Model provider failure: %s", type(error).__name__)
        raise HTTPException(502, "Model provider request failed; check credentials, quota and connectivity.") from None
    except (ValueError, TypeError, KeyError, IndexError):
        raise HTTPException(502, "The model returned an invalid decision; retry this stochastic run.") from None
    except RuntimeError:
        raise HTTPException(503, "Model runtime is unavailable; check configuration.") from None
    finally:
        workflow_slots.release()


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Keep actionable schema locations, without echoing request bodies or parser context.
    details = [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in error.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(Exception)
async def internal_error(request, error):
    # Do not expose provider bodies, secrets, prompts or tracebacks to the browser.
    logging.getLogger(__name__).error("Request failed: %s", type(error).__name__)
    return JSONResponse(status_code=500, content={"success": False, "error": "Request failed; inspect server configuration and storage."})


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    with get_connection() as connection:
        connection.execute("SELECT id FROM regressions LIMIT 1")
    configuration = model_configuration()
    return JSONResponse(status_code=200 if configuration["configured"] else 503,
                        content={"status": "ready" if configuration["configured"] else "unconfigured",
                                 "storage": "available", **configuration,
                                 "provider_connectivity": "not_checked"})


@app.get("/api/categories")
def get_categories(domain: str = "customer_support"):
    if domain not in {"customer_support", "emergency_response"}:
        raise HTTPException(400, "Unsupported domain")
    categories = emergency.CATEGORIES if domain == "emergency_response" else CATEGORIES
    return {"categories": [{"id": key, "name": value[0], "severity": value[1],
                            "description": value[2], "replay_supported": key in REPLAY_ADAPTERS or key in emergency.CATEGORIES}
                           for key, value in categories.items()]}


@app.post("/api/investigate/{category}")
def investigate(category: str):
    if category not in CATEGORIES and category not in emergency.CATEGORIES:
        raise HTTPException(400, "Unsupported investigation category")
    with model_workflow():
        result = emergency.investigate(category) if category in emergency.CATEGORIES else run_forensics(category)
    result["schema_version"] = "1.0"
    result["model_configuration"] = model_configuration()
    result["limitations"] = (["Controlled simulated emergency actions", "Frozen USGS data; not live", "Exact-case stochastic replay", "Rule-based evaluation"] if category in emergency.CATEGORIES else ["Controlled customer-support sandbox", "Injection attribution is temporal evidence, not causal proof",
                             "Minimization is empirically validated, not globally minimal"])
    return {"success": True, "category": category, "result": result}


def execute_replay(category: str, message: str, regression_id=None, scenario=None):
    if category in emergency.CATEGORIES:
        emergency.frozen_case(category, scenario)
        with model_workflow():
            result, verification = emergency.replay(category, message, scenario)
        run_id = str(uuid4())
        payload = {"success": True, "schema_version": "1.0", "category": category,
                   "domain": "emergency_response", "replay_id": run_id, "result": result,
                   "verification": verification, "model_configuration": model_configuration(),
                   "scope": "Fresh baseline and protected simulated execution; exact-case stochastic replay."}
        save_replay_run(run_id, category, payload, regression_id)
        return payload
    if category not in REPLAY_ADAPTERS:
        raise HTTPException(400, "Replay is not yet supported for this investigation category")
    adapter, guardrail = REPLAY_ADAPTERS[category]
    if scenario is not None:
        from backend.app.sandbox.scenarios import validate_scenario
        try:
            scenario = validate_scenario(scenario)
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid scenario fixture") from None
        if category not in {"identity_bypass", "false_action_claim"}:
            raise HTTPException(422, "Scenario fixtures are supported only for identity and action replay")
    with model_workflow():
        result = adapter(message, scenario=scenario) if scenario is not None else adapter(message)
    expected = PRIMARY_FAILURE_BY_CATEGORY[category]
    before = result["before_fix"]
    after = result["after_fix"]
    before_failed = bool(before["failed"])
    after_failed = bool(after["failed"])
    reproduced = any(item["violation"] == expected for item in before["violations"])
    completed = all(side["agent_result"].get("completed", False) for side in (before, after))
    verification = {"before_failed": before_failed, "after_failed": after_failed,
                    "reproduced": reproduced, "completed": completed,
                    "mitigation_verified": reproduced and before_failed and not after_failed and completed}
    run_id = str(uuid4())
    payload = {"success": True, "schema_version": "1.0", "category": category,
               "replay_id": run_id, "result": result, "verification": verification,
               "model_configuration": model_configuration(),
               "scope": "One baseline and one protected LLM execution of this exact trigger; no universal guarantee."}
    save_replay_run(run_id, category, payload, regression_id)
    return payload


@app.post("/api/replay/{category}")
def replay(category: str, request: ReplayRequest):
    return execute_replay(category, request.message, scenario=request.scenario)


@app.post("/api/regressions")
def create_regression(request: RegressionRequest):
    receipt = get_replay_run(request.replay_id)
    if receipt is None or receipt["category"] != request.category:
        raise HTTPException(409, "A matching server replay record is required")
    payload = receipt["payload"]
    evidence = payload["result"]
    expected = emergency.EXPECTED.get(request.category) or PRIMARY_FAILURE_BY_CATEGORY.get(request.category)
    expected_guardrail = emergency.GUARDRAIL if request.category in emergency.CATEGORIES else REPLAY_ADAPTERS.get(request.category, (None, None))[1]
    before = [item["violation"] for item in evidence["before_fix"]["violations"]]
    after = [item["violation"] for item in evidence["after_fix"]["violations"]]
    if (not payload["verification"]["mitigation_verified"]
        or request.minimal_trigger != evidence["trigger"]
        or request.guardrail != expected_guardrail or request.failure_class != expected
        or request.status != "verified" or not request.mitigation_verified
        or sorted(request.before_violations) != sorted(before) or sorted(request.after_violations) != sorted(after)):
        raise HTTPException(409, "Regression fields must match a completed, verified server replay")
    saved = save_regression_case(request.category, expected, request.original_trigger,
                                 evidence["trigger"], expected_guardrail, "verified", True, before, after, scenario=evidence.get("scenario", {}))
    # Associate the existing evidence with the saved case without another model call.
    with get_connection() as connection:
        connection.execute("UPDATE replay_runs SET regression_id = ? WHERE id = ?", (saved["id"], request.replay_id))
    return {"success": True, "regression": emergency.annotate(saved)}


@app.get("/api/regressions")
def get_regressions():
    cases = list_regression_cases()
    return {"success": True, "count": len(cases), "regressions": [emergency.annotate(case) for case in cases]}


@app.get("/api/regressions/{regression_id}/report")
def regression_report(regression_id: int):
    case = get_regression_case(regression_id)
    if case is None:
        raise HTTPException(404, "Regression not found")
    return {"schema_version": "1.0", "regression": emergency.annotate(case), "replay_runs": list_replay_runs(regression_id),
            "legacy_evidence": "Cases saved before v0.2 contain summaries; rerun to store full trace evidence."}


@app.post("/api/regressions/{regression_id}/rerun")
def rerun_regression(regression_id: int):
    case = get_regression_case(regression_id)
    if case is None:
        raise HTTPException(404, "Regression not found")
    if case["category"] in emergency.CATEGORIES:
        if case["guardrail"] != emergency.GUARDRAIL or case["failure_class"] != emergency.EXPECTED[case["category"]]:
            raise HTTPException(409, "Saved case has no compatible replay adapter")
        return execute_replay(case["category"], case["minimal_trigger"], regression_id, scenario=case.get("scenario") or None)
    adapter = REPLAY_ADAPTERS.get(case["category"])
    if adapter is None or case["guardrail"] != adapter[1] or case["failure_class"] != PRIMARY_FAILURE_BY_CATEGORY[case["category"]]:
        raise HTTPException(409, "Saved case has no compatible replay adapter")
    return execute_replay(case["category"], case["minimal_trigger"], regression_id, scenario=case.get("scenario") or None)


FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(FRONTEND / "index.html")
