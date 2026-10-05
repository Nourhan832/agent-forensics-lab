import os

# Tests cannot load local credentials and cannot write to the working database.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["NEBIUS_API_KEY"] = "offline-test-only"
os.environ["NEBIUS_BASE_URL"] = "https://example.invalid/v1"
os.environ["NEBIUS_MODEL"] = "offline-test-model"

import pytest
from fastapi.testclient import TestClient
from backend.app.api import main
from backend.app.integrations import nemotron
from backend.app.storage import regressions


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(regressions, "DATABASE_PATH", tmp_path / "regressions.db")
    def no_network():
        raise AssertionError("Offline tests must stub model responses; live requests are forbidden")
    monkeypatch.setattr(nemotron, "get_client", no_network)
    regressions.initialize_regression_storage()


@pytest.fixture
def client():
    with TestClient(main.app) as value:
        yield value
