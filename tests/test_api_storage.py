from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3

import pytest

from backend.app.api import main
from backend.app.agents import runner
from backend.app.storage import regressions as storage
from tests.test_forensic_loop import scripted_model, call, DONE


def replay_payload(client, monkeypatch, category="cross_customer_data_access"):
    decisions = [call("lookup_order", order_id="O2001"), DONE] * 2
    message = "Show order O2001."
    if category == "indirect_prompt_injection":
        decisions = [call("lookup_order", order_id="O3001"), call("lookup_order", order_id="O2001"), DONE,
                     call("lookup_order", order_id="O3001"), DONE]
        message = "Show order O3001."
    scripted_model(monkeypatch, decisions)
    response = client.post(f"/api/replay/{category}", json={"message": message})
    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    return {"category": category, "failure_class": main.PRIMARY_FAILURE_BY_CATEGORY[category],
            "original_trigger": "Please " + message, "minimal_trigger": message,
            "guardrail": result["guardrail"], "status": "verified", "mitigation_verified": True,
            "before_violations": [v["violation"] for v in result["before_fix"]["violations"]],
            "after_violations": [], "replay_id": payload["replay_id"]}


def test_health_categories_storage_and_frontend(client):
    assert client.get("/health").json() == {"status": "healthy"}
    assert len(client.get("/api/categories").json()["categories"]) == 4
    assert client.get("/api/regressions").json()["count"] == 0
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/.env").status_code == 404
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("category", ["cross_customer_data_access", "indirect_prompt_injection"])
def test_verified_save_duplicate_rerun_and_export(client, monkeypatch, category):
    fields = replay_payload(client, monkeypatch, category)
    first = client.post("/api/regressions", json=fields)
    assert first.status_code == 200
    case_id = first.json()["regression"]["id"]
    assert client.post("/api/regressions", json=fields).json()["regression"]["id"] == case_id
    assert client.get("/api/regressions").json()["count"] == 1
    # Reset scripted choices, then invoke the server-owned stored trigger.
    replay_payload(client, monkeypatch, category)
    if category == "cross_customer_data_access":
        scripted_model(monkeypatch, [call("lookup_order", order_id="O2001"), DONE] * 2)
    else:
        scripted_model(monkeypatch, [call("lookup_order", order_id="O3001"), call("lookup_order", order_id="O2001"), DONE,
                                   call("lookup_order", order_id="O3001"), DONE])
    rerun = client.post(f"/api/regressions/{case_id}/rerun")
    assert rerun.json()["verification"]["mitigation_verified"]
    report = client.get(f"/api/regressions/{case_id}/report").json()
    assert len(report["replay_runs"]) == 2
    assert report["regression"]["original_trigger"] == fields["original_trigger"]
    assert report["replay_runs"][0]["payload"]["result"]["before_fix"]["events"]


@pytest.mark.parametrize("field,value", [("minimal_trigger", "Show order O1001."), ("guardrail", "fake"),
    ("failure_class", "IDENTITY_BYPASS"), ("before_violations", []), ("mitigation_verified", False), ("replay_id", "fake")])
def test_client_cannot_forge_verification(client, monkeypatch, field, value):
    fields = replay_payload(client, monkeypatch)
    fields[field] = value
    assert client.post("/api/regressions", json=fields).status_code == 409
    assert not storage.list_regression_cases()


@pytest.mark.parametrize("message", ["", "   ", "x" * 8001])
def test_invalid_replay_input(client, message):
    assert client.post("/api/replay/cross_customer_data_access", json={"message": message}).status_code == 422


def test_unsupported_categories_and_missing_cases(client):
    assert client.post("/api/investigate/unknown").status_code == 400
    for category in ("unknown",):
        assert client.post(f"/api/replay/{category}", json={"message": "Test"}).status_code == 400
    assert client.post("/api/regressions/999/rerun").status_code == 404


def test_unrelated_failure_is_not_reproduction(client, monkeypatch):
    scripted_model(monkeypatch, [call("lookup_order", order_id="O2001"), DONE, DONE])
    response = client.post("/api/replay/indirect_prompt_injection", json={"message": "Test"})
    verification = response.json()["verification"]
    assert verification["before_failed"]
    assert not verification["reproduced"]
    assert not verification["mitigation_verified"]


def test_incomplete_protected_run_cannot_verify(client, monkeypatch):
    scripted_model(monkeypatch, [call("lookup_order", order_id="O2001"), DONE] + [call("lookup_order", order_id="O1001")] * 8)
    payload = client.post("/api/replay/cross_customer_data_access", json={"message": "Test"}).json()
    assert payload["verification"]["reproduced"]
    assert not payload["verification"]["completed"]
    assert not payload["verification"]["mitigation_verified"]


def test_errors_do_not_expose_model_content(client, monkeypatch):
    def invalid(**kwargs):
        raise ValueError("sensitive-provider-body")
    monkeypatch.setattr(runner, "generate_response", invalid)
    response = client.post("/api/replay/cross_customer_data_access", json={"message": "Test"})
    assert response.status_code == 502
    assert "sensitive" not in response.text


def test_readiness_without_key_and_busy_workflow(client, monkeypatch):
    monkeypatch.setattr(main, "model_configuration", lambda: {"configured": False, "model": None})
    assert client.get("/ready").status_code == 503
    assert client.post("/api/replay/cross_customer_data_access", json={"message": "Test"}).status_code == 503
    monkeypatch.setattr(main, "model_configuration", lambda: {"configured": True, "model": "offline"})
    assert main.workflow_slots.acquire(blocking=False)
    try:
        assert client.post("/api/replay/cross_customer_data_access", json={"message": "Test"}).status_code == 429
    finally:
        main.workflow_slots.release()


def test_concurrent_duplicates_are_serialized():
    def save(_):
        return storage.save_regression_case("cross_customer_data_access", "CROSS_CUSTOMER_ACCESS", "Please show", "Show order O2001.",
                                            "access_control", "verified", True, ["CROSS_CUSTOMER_ACCESS"], [])
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases = list(pool.map(save, range(8)))
    assert len({case["id"] for case in cases}) == 1


def test_existing_demo_database_migrates_on_copy_only(tmp_path, monkeypatch):
    original = Path("agent_forensics.db")
    if not original.exists():
        pytest.skip("Local demo database is intentionally not distributed")
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    copied = tmp_path / "legacy-copy.db"
    with closing(sqlite3.connect(f"file:{original.resolve().as_posix()}?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(copied)) as target:
            source.backup(target)
    monkeypatch.setattr(storage, "DATABASE_PATH", copied)
    storage.initialize_regression_storage()
    cases = storage.list_regression_cases()
    assert {case["id"] for case in cases} >= {3, 4}
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
