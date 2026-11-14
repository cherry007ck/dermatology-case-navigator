"""Integration: the voice adapter against Zoro's real EncounterService (memory repository).

Same code path as Exasol mode except the repository. Proves the adapter needs nothing
beyond the frozen get_session/advance seam after the S1 backend merge.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.intake_service import get_intake_service
from app.main import create_app
from app.service import EncounterService
from app.voice.advance import SPOKEN_READY, VoiceAdvancer, get_voice_advancer
from app.voice.bindings import VoiceBindingStore, get_binding_store
from app.voice.router import get_voice_tool_secret
from tests.conftest import DEMO_CODE, memory_service

SECRET = "test-tool-secret-not-real"
MAIN = [
    "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
    "I don't remember the name. I used it for a few days.",
    "I started using a new hand soap before this began.",
]


def make_client() -> tuple[TestClient, EncounterService]:
    app = create_app()
    service = memory_service()
    store = VoiceBindingStore()
    advancer = VoiceAdvancer(wait_seconds=0, sleep=lambda _: None)
    app.dependency_overrides[get_intake_service] = lambda: service
    app.dependency_overrides[get_binding_store] = lambda: store
    app.dependency_overrides[get_voice_tool_secret] = lambda: SECRET
    app.dependency_overrides[get_voice_advancer] = lambda: advancer
    return TestClient(app), service


def test_voice_loop_through_encounter_service() -> None:
    client, _ = make_client()
    created = client.post("/v1/sessions", headers=DEMO_CODE,
                          json={"request_id": str(uuid.uuid4()), "collection_id": "synthetic-demo-v1"}).json()
    sid, auth = created["session_id"], {"Authorization": f"Bearer {created['session_token']}"}
    binding = client.post(f"/v1/sessions/{sid}/voice-binding", headers=auth,
                          json={"request_id": str(uuid.uuid4()), "expected_revision": 0}).json()["binding_token"]
    tool = {"X-Tool-Secret": SECRET, "X-Voice-Binding": binding}

    def say(text: str, n: int, role: str = "patient") -> None:
        revision = client.get(f"/v1/sessions/{sid}", headers=auth).json()["revision"]
        res = client.post(f"/v1/sessions/{sid}/turns", headers=auth, json={
            "request_id": str(uuid.uuid4()), "expected_revision": revision,
            "turns": [{"turn_id": f"voice-c1-{role}-{n}", "role": role, "origin": "voice_transcript",
                       "text": text, "reply_to_question_id": None}]})
        assert res.status_code == 200, res.text

    say("Fictional greeting from the agent.", 0, role="agent")
    say(MAIN[0], 1)
    first = client.post("/v1/voice/advance", json={}, headers=tool).json()
    assert first["action"] == "ask" and first["question_text"] == first["spoken_message"]
    assert client.post("/v1/voice/advance", json={}, headers=tool).json() == first  # no second question

    say(MAIN[1], 2)
    assert client.post("/v1/voice/advance", json={}, headers=tool).json()["action"] == "ask"
    say(MAIN[2], 3)
    last = client.post("/v1/voice/advance", json={}, headers=tool).json()
    assert last == {"action": "ready_to_confirm", "question_id": None, "question_text": None, "spoken_message": SPOKEN_READY}

    snap = client.get(f"/v1/sessions/{sid}", headers=auth).json()
    assert snap["revision"] == 3  # the agent turn did not bump the patient revision
    assert snap["state"] == "ready_to_confirm"


def test_duplicate_voice_event_is_rejected_by_the_real_service() -> None:
    client, _ = make_client()
    created = client.post("/v1/sessions", headers=DEMO_CODE,
                          json={"request_id": str(uuid.uuid4()), "collection_id": "synthetic-demo-v1"}).json()
    sid, auth = created["session_id"], {"Authorization": f"Bearer {created['session_token']}"}
    turn = {"turn_id": "voice-c1-patient-1", "role": "patient", "origin": "voice_transcript",
            "text": MAIN[0], "reply_to_question_id": None}
    ok = client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                     json={"request_id": str(uuid.uuid4()), "expected_revision": 0, "turns": [turn]})
    again = client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                        json={"request_id": str(uuid.uuid4()), "expected_revision": 1, "turns": [turn]})
    assert ok.status_code == 200
    assert again.status_code == 409 and again.json()["error"]["code"] == "DUPLICATE_TURN_ID"  # browser treats as saved
