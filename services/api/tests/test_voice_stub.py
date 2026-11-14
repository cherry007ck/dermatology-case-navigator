"""Voice module (Luffy): scoped bindings and webhook authentication. The question flow is S2."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.intake_service import get_intake_service
from app.main import create_app
from app.stub_service import FixtureStubIntakeService
from app.voice.advance import VoiceAdvancer, get_voice_advancer
from app.voice.bindings import BINDING_TTL, VoiceBindingStore, get_binding_store
from app.voice.router import get_voice_tool_secret
from tests.conftest import DEMO_CODE

TOOL_SECRET = "test-tool-secret-not-real"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def voice_client(clock: Clock) -> TestClient:
    app = create_app()
    service = FixtureStubIntakeService()
    store = VoiceBindingStore(now=clock)
    # No real waiting in tests: the bounded transcript wait is exercised in test_voice_advance.py.
    advancer = VoiceAdvancer(wait_seconds=0, sleep=lambda _: None)
    app.dependency_overrides[get_intake_service] = lambda: service
    app.dependency_overrides[get_binding_store] = lambda: store
    app.dependency_overrides[get_voice_tool_secret] = lambda: TOOL_SECRET
    app.dependency_overrides[get_voice_advancer] = lambda: advancer
    return TestClient(app)


def new_session(client: TestClient) -> tuple[str, dict]:
    body = client.post("/v1/sessions", headers=DEMO_CODE,
                       json={"request_id": str(uuid.uuid4()), "collection_id": "synthetic-demo-v1"}).json()
    return body["session_id"], {"Authorization": f"Bearer {body['session_token']}"}


def bind(client: TestClient, sid: str, auth: dict, revision: int = 0, request_id: str | None = None):
    return client.post(f"/v1/sessions/{sid}/voice-binding", headers=auth,
                       json={"request_id": request_id or str(uuid.uuid4()), "expected_revision": revision})


def advance(client: TestClient, secret: str | None, binding: str | None):
    headers = {k: v for k, v in {"X-Tool-Secret": secret, "X-Voice-Binding": binding}.items() if v is not None}
    return client.post("/v1/voice/advance", json={}, headers=headers)


def test_binding_requires_valid_session_token(voice_client: TestClient) -> None:
    sid, _ = new_session(voice_client)
    assert bind(voice_client, sid, {}).status_code == 401
    assert bind(voice_client, sid, {"Authorization": "Bearer wrong"}).status_code == 404
    _, other_auth = new_session(voice_client)
    assert bind(voice_client, sid, other_auth).status_code == 404  # another session's token


def test_binding_issued_scoped_and_expiring(voice_client: TestClient, clock: Clock) -> None:
    sid, auth = new_session(voice_client)
    res = bind(voice_client, sid, auth)
    assert res.status_code == 200
    body = res.json()
    assert body["binding_token"].startswith("vb_") and len(body["binding_token"]) > 40
    assert body["binding_token"] not in str(voice_client.get(f"/v1/sessions/{sid}", headers=auth).json())
    expires = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    assert expires - clock.now == BINDING_TTL


def test_stale_revision_issues_nothing(voice_client: TestClient) -> None:
    sid, auth = new_session(voice_client)
    res = bind(voice_client, sid, auth, revision=5)
    assert res.status_code == 409 and res.json()["error"]["code"] == "REVISION_CONFLICT"


def test_binding_retry_is_idempotent(voice_client: TestClient) -> None:
    sid, auth = new_session(voice_client)
    request_id = str(uuid.uuid4())
    first = bind(voice_client, sid, auth, request_id=request_id).json()
    again = bind(voice_client, sid, auth, request_id=request_id).json()
    assert first == again
    assert bind(voice_client, sid, auth, revision=1, request_id=request_id).status_code == 409


def test_webhook_needs_secret_and_live_binding(voice_client: TestClient, clock: Clock) -> None:
    sid, auth = new_session(voice_client)
    binding = bind(voice_client, sid, auth).json()["binding_token"]
    for secret, token in [(None, None), (TOOL_SECRET, None), (None, binding), ("wrong", binding), (TOOL_SECRET, "vb_forged")]:
        res = advance(voice_client, secret, token)
        assert res.status_code == 401 and res.json()["error"]["code"] == "VOICE_AUTH_FAILED", (secret, token)
    # Both valid: authenticated; nothing persisted yet, so the agent is told to wait.
    ok = advance(voice_client, TOOL_SECRET, binding)
    assert ok.status_code == 200 and ok.json()["action"] == "waiting_for_transcript"
    clock.now += BINDING_TTL + timedelta(seconds=1)
    assert advance(voice_client, TOOL_SECRET, binding).status_code == 401  # expired -> reconnect


def test_new_binding_revokes_previous(voice_client: TestClient) -> None:
    sid, auth = new_session(voice_client)
    old = bind(voice_client, sid, auth).json()["binding_token"]
    new = bind(voice_client, sid, auth).json()["binding_token"]
    assert old != new
    assert advance(voice_client, TOOL_SECRET, old).status_code == 401
    assert advance(voice_client, TOOL_SECRET, new).status_code == 200


def test_webhook_fails_closed_without_configured_secret(voice_client: TestClient) -> None:
    voice_client.app.dependency_overrides[get_voice_tool_secret] = lambda: ""
    res = advance(voice_client, "", "anything")
    assert res.status_code == 503 and res.json()["error"]["code"] == "VOICE_TOOL_NOT_CONFIGURED"


def test_store_binding_tokens_are_never_stored_raw() -> None:
    store = VoiceBindingStore()
    issued = store.issue("S-1", "r-1", "h", session_token="bearer-not-real")
    assert issued.binding_token not in repr(store.__dict__)
    assert "bearer-not-real" not in repr(store._by_hash)  # bearer excluded from reprs
    resolved = store.resolve(issued.binding_token)
    assert resolved is not None and resolved.session_id == "S-1"
    assert "bearer-not-real" not in repr(resolved)
    store.revoke_session("S-1")
    assert store.resolve(issued.binding_token) is None
    assert all(b.session_token is None for b in store._by_hash.values())  # bearer dropped on revoke
