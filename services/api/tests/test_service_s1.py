"""S1 encounter service: persistence seam, idempotency, concurrency and storage failure modes.

These run on the memory repository, which implements the same ``EncounterRepository`` contract as
Exasol. ``tests/test_exasol_live.py`` runs the Exasol repository itself when credentials exist.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import ApiError
from app.extraction.rules import RuleCandidateProvider
from app.pipeline import IntakePipeline
from app.fixtures import get_fixture_bundle
from app.intake_service import _build_service, get_intake_service
from app.main import create_app
from app.models import AdvanceRequest, AppendTurnsRequest, CreateSessionRequest, TurnInput
from app.repositories.base import ConcurrentModification, StorageUnavailable
from app.repositories.memory import MemoryEncounterRepository
from app.service import EncounterService
from tests.conftest import DEMO_CODE

TEXT = "My hands have been itchy for weeks. I tried a cream, but it didn't help."
SECRET = "test-session-secret-not-real"


def rid() -> str:
    return str(uuid.uuid4())


def repo() -> MemoryEncounterRepository:
    bundle = get_fixture_bundle()
    return MemoryEncounterRepository(bundle.collection, bundle.cases)


def service(repository, settings=None) -> EncounterService:
    return EncounterService(settings or get_settings(), repository, IntakePipeline(RuleCandidateProvider()),
                            token_secret=SECRET)


def turn(text: str = TEXT) -> TurnInput:
    return TurnInput(turn_id=f"t-{uuid.uuid4()}", role="patient", origin="typed", text=text,
                     reply_to_question_id=None)


def test_encounter_survives_a_new_service_instance() -> None:
    shared = repo()
    first = service(shared)
    created = first.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))
    first.append_turns(created.session_id, created.session_token,
                       AppendTurnsRequest(request_id=rid(), expected_revision=0, turns=[turn()]))
    first.advance(created.session_id, AdvanceRequest(request_id=rid(), expected_revision=1))

    restarted = service(shared)  # new process state, same storage and stable secret
    snap = restarted.get_session(created.session_id, created.session_token)
    assert snap.revision == 1 and len(snap.turns) == 1 and len(snap.search_history) == 1
    assert snap.state == "awaiting_answer" and snap.brief is not None


def test_create_retry_returns_the_original_response_after_later_changes() -> None:
    svc = service(repo())
    request = CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1")
    original = svc.create_session(request)
    svc.append_turns(original.session_id, original.session_token,
                     AppendTurnsRequest(request_id=rid(), expected_revision=0, turns=[turn()]))
    retried = svc.create_session(request)
    assert retried.session_id == original.session_id and retried.session_token == original.session_token
    assert retried.snapshot == original.snapshot  # original response, not the current state


def test_concurrent_modification_is_a_conflict_not_an_overwrite() -> None:
    shared = repo()
    svc = service(shared)
    created = svc.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))
    real_commit = shared.commit

    def stale_commit(batch):
        raise ConcurrentModification(batch.record.session_id)

    shared.commit = stale_commit  # type: ignore[method-assign]
    with pytest.raises(ApiError) as err:
        svc.append_turns(created.session_id, created.session_token,
                         AppendTurnsRequest(request_id=rid(), expected_revision=0, turns=[turn()]))
    assert err.value.status_code == 409 and err.value.code == "REVISION_CONFLICT"
    shared.commit = real_commit  # type: ignore[method-assign]
    assert svc.get_session(created.session_id, created.session_token).revision == 0


def test_storage_failure_is_a_retryable_503_without_details() -> None:
    shared = repo()
    svc = service(shared)
    created = svc.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))

    def down(*_args, **_kwargs):
        raise StorageUnavailable("connection to host xyz failed")

    shared.load_session = down  # type: ignore[method-assign]
    request = AppendTurnsRequest(request_id=rid(), expected_revision=0, turns=[turn()])
    with pytest.raises(ApiError) as err:
        svc.append_turns(created.session_id, created.session_token, request)
    assert (err.value.status_code, err.value.code, err.value.retryable) == (503, "STORAGE_UNAVAILABLE", True)
    assert "xyz" not in err.value.message and err.value.request_id == request.request_id


def test_readiness_reports_not_ready_when_storage_is_down() -> None:
    shared = repo()

    def down():
        raise StorageUnavailable("down")

    shared.ping = down  # type: ignore[method-assign]
    ready = service(shared).readiness()
    assert ready.ready is False and ready.storage == "memory" and ready.loaded_cases == 0


def test_advance_requires_the_referenced_cases_in_storage() -> None:
    bundle = get_fixture_bundle()
    empty = MemoryEncounterRepository(bundle.collection, [])  # collection row without its cases
    svc = service(empty)
    created = svc.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))
    svc.append_turns(created.session_id, created.session_token,
                     AppendTurnsRequest(request_id=rid(), expected_revision=0, turns=[turn()]))
    with pytest.raises(ApiError) as err:
        svc.advance(created.session_id, AdvanceRequest(request_id=rid(), expected_revision=1))
    assert err.value.code == "COLLECTION_UNAVAILABLE"
    assert svc.get_session(created.session_id, created.session_token).search_history == []


def test_expired_session_is_not_found() -> None:
    shared = repo()
    svc = service(shared)
    created = svc.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))
    stored = shared._sessions[created.session_id]
    stored.expires_at = stored.created_at - timedelta(seconds=1)
    with pytest.raises(ApiError) as err:
        svc.get_session(created.session_id, created.session_token)
    assert err.value.status_code == 404


def test_published_mode_hides_the_synthetic_collection() -> None:
    svc = service(repo(), replace(get_settings(), collection_mode="published"))
    assert svc.list_collections().collections == []
    with pytest.raises(ApiError) as err:
        svc.create_session(CreateSessionRequest(request_id=rid(), collection_id="synthetic-demo-v1"))
    assert err.value.status_code == 404


def test_exasol_mode_without_configuration_never_falls_back_to_memory(monkeypatch) -> None:
    settings = replace(get_settings(), data_backend="exasol", exasol_dsn="", exasol_user="", exasol_password="")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    _build_service.cache_clear()
    try:
        with pytest.raises(ApiError) as err:
            get_intake_service()
        assert err.value.status_code == 503 and err.value.code == "STORAGE_NOT_CONFIGURED"
        res = TestClient(create_app()).get("/v1/readiness", headers=DEMO_CODE)
        assert res.status_code == 503 and res.json()["error"]["code"] == "STORAGE_NOT_CONFIGURED"
    finally:
        _build_service.cache_clear()


def test_exasol_mode_requires_a_stable_session_secret() -> None:
    from app.repositories.exasol import ExasolEncounterRepository

    exasol = ExasolEncounterRepository("host.invalid:8563", "user", "not-a-real-token")  # never connects here
    with pytest.raises(RuntimeError):
        EncounterService(get_settings(), exasol, IntakePipeline(RuleCandidateProvider()), token_secret="")


def test_http_snapshot_reports_actual_storage_and_labels(client: TestClient) -> None:
    created = client.post("/v1/sessions", headers=DEMO_CODE,
                          json={"request_id": rid(), "collection_id": "synthetic-demo-v1"}).json()
    snap = created["snapshot"]
    assert snap["modes"] == {"storage": "memory", "extractor": "fixture"}
    assert any("Demo extraction" in w for w in snap["warnings"])
    assert any("not Exasol" in w for w in snap["warnings"])
