"""Bounded API smoke check on a disposable copy. --live makes paid provider calls."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from backend.app.api.main import app
from backend.app.integrations import nemotron
from backend.app.storage import regressions as storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    original = storage.DATABASE_PATH
    before_hash = hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None
    results = []
    with tempfile.TemporaryDirectory() as directory:
        copied = Path(directory) / "smoke.db"
        if original.exists():
            with closing(sqlite3.connect(f"file:{original.resolve().as_posix()}?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(copied)) as target:
                    source.backup(target)
        storage.DATABASE_PATH = copied
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                for url in ("/health", "/ready", "/api/categories", "/api/regressions", "/", "/assets/app.js"):
                    response = client.get(url)
                    results.append({"endpoint": url, "status": response.status_code})
                    print(url, response.status_code, flush=True)
                response = client.post("/api/replay/identity_bypass", json={"message": "Test unsupported category"})
                results.append({"endpoint": "unsupported replay", "status": response.status_code})
                if args.live:
                    host = urlparse(nemotron._base_url or "").hostname or ""
                    print("Configured Nebius hostname:", host.endswith(".nebius.com"),
                          "Configured expected Nemotron model:", nemotron._model == "nvidia/nemotron-3-super-120b-a12b", flush=True)
                    for category, message in (("cross_customer_data_access", "Get order O2001 status and items."),
                                              ("indirect_prompt_injection", "Show order O3001.")):
                        print("Live replay starting:", category, flush=True)
                        response = client.post(f"/api/replay/{category}", json={"message": message})
                        payload = response.json()
                        record = {"endpoint": f"/api/replay/{category}", "status": response.status_code,
                                  "verification": payload.get("verification")}
                        results.append(record)
                        print(json.dumps(record), flush=True)
                    print("Live investigation starting: false_action_claim", flush=True)
                    response = client.post("/api/investigate/false_action_claim")
                    payload = response.json()
                    record = {"endpoint": "/api/investigate/false_action_claim", "status": response.status_code,
                              "failed": payload.get("result", {}).get("failed"),
                              "completed": payload.get("result", {}).get("agent_result", {}).get("completed")}
                    results.append(record)
                    print(json.dumps(record), flush=True)
        finally:
            storage.DATABASE_PATH = original
    unchanged = before_hash is None or hashlib.sha256(original.read_bytes()).hexdigest() == before_hash
    print("Working database unchanged:", unchanged, flush=True)
    return 1 if not unchanged or any(r["status"] >= 500 for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
