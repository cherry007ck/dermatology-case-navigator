from __future__ import annotations

import os

# Unit tests must not depend on a developer's services/api/.env. These values are set before
# app.config loads .env (which never overrides existing variables). EXASOL_* is left alone so the
# opt-in live test (tests/test_exasol_live.py) can still read local credentials.
os.environ.update({
    "APP_ENV": "test",
    "DATA_BACKEND": "memory",
    "EXTRACTOR_MODE": "fixture",
    "COLLECTION_MODE": "synthetic",
    "DEMO_ACCESS_CODE": "",  # development/test then accepts the documented code "local-demo"
    "EXASOL_TELEMETRY_DISABLE": "1",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.extraction.rules import RuleCandidateProvider
from app.pipeline import IntakePipeline  # noqa: E402
from app.fixtures import get_fixture_bundle  # noqa: E402
from app.intake_service import get_intake_service  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.memory import MemoryEncounterRepository  # noqa: E402
from app.service import EncounterService  # noqa: E402

DEMO_CODE = {"X-Demo-Access-Code": "local-demo"}


def memory_service() -> EncounterService:
    """Fresh S1 service over a memory repository (same code path as Exasol mode)."""
    bundle = get_fixture_bundle()
    return EncounterService(
        get_settings(), MemoryEncounterRepository(bundle.collection, bundle.cases), IntakePipeline(RuleCandidateProvider())
    )


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    service = memory_service()  # fresh memory store per test
    app.dependency_overrides[get_intake_service] = lambda: service
    return TestClient(app)
