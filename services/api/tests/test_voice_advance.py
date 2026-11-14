"""advance_intake webhook (Luffy's voice module) against the shared S0 stub service.

The stub replays contract examples for the documented fictional phrases, so these
tests prove the adapter's auth, wait, idempotency and voice-safe mapping; they do not
prove real extraction (Zoro's pipeline).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.intake_service import get_intake_service
from app.main import create_app
from app.stub_service import FixtureStubIntakeService
from app.voice.advance import SPOKEN_READY, VoiceAdvancer, get_voice_advancer
from app.voice.bindings import VoiceBindingStore, get_binding_store
from app.voice.router import get_voice_tool_secret
from tests.conftest import DEMO_CODE

SECRET = "test-tool-secret-not-real"
MAIN = [
    "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
    "I don't remember the name. I used it for a few days.",
    "I started using a new hand soap before this began.",
]
VOICE_KEYS = {"action", "question_id", "question_text", "spoken_message"}


class Harness:
    def __init__(self, wait_seconds: float = 0.0) -> None:
        self.app = create_app()
        self.service = FixtureStubIntakeService()
        self.on_sleep = None  # hook to simulate a transcript landing during the wait
        self.time = 0.0

        def sleep(seconds: float) -> None:
            self.time += seconds
            if self.on_sleep:
                hook, self.on_sleep = self.on_sleep, None
                hook()

        self.advancer = VoiceAdvancer(wait_seconds=wait_seconds, poll_seconds=0.2, sleep=sleep, clock=lambda: self.time)
        store = VoiceBindingStore()
        self.app.dependency_overrides[get_intake_service] = lambda: self.service
        self.app.dependency_overrides[get_binding_store] = lambda: store
        self.app.dependency_overrides[get_voice_tool_secret] = lambda: SECRET
        self.app.dependency_overrides[get_voice_advancer] = lambda: self.advancer
        self.client = TestClient(self.app)

    def session(self) -> tuple[str, dict, str]:
        body = self.client.post("/v1/sessions", headers=DEMO_CODE,
                                json={"request_id": str(uuid.uuid4()), "collection_id": "synthetic-demo-v1"}).json()
        auth = {"Authorization": f"Bearer {body['session_token']}"}
        binding = self.client.post(f"/v1/sessions/{body['session_id']}/voice-binding", headers=auth,
                                   json={"request_id": str(uuid.uuid4()), "expected_revision": 0}).json()
        return body["session_id"], auth, binding["binding_token"]

    def say(self, sid: str, auth: dict, text: str, *, turn_id: str | None = None, role: str = "patient",
            reply_to: str | None = None) -> dict:
        revision = self.client.get(f"/v1/sessions/{sid}", headers=auth).json()["revision"]
        res = self.client.post(f"/v1/sessions/{sid}/turns", headers=auth, json={
            "request_id": str(uuid.uuid4()), "expected_revision": revision,
            "turns": [{"turn_id": turn_id or f"voice-c1-{role}-{uuid.uuid4()}", "role": role,
                       "origin": "voice_transcript", "text": text, "reply_to_question_id": reply_to}],
        })
        assert res.status_code == 200, res.text
        return res.json()

    def tool(self, binding: str, body: dict | None = None):
        return self.client.post("/v1/voice/advance", json=body or {},
                                headers={"X-Tool-Secret": SECRET, "X-Voice-Binding": binding})


@pytest.fixture
def h() -> Harness:
    return Harness()


def test_full_voice_loop_returns_only_voice_safe_fields(h: Harness) -> None:
    sid, auth, binding = h.session()
    h.say(sid, auth, MAIN[0])
    first = h.tool(binding).json()
    assert set(first) == VOICE_KEYS
    assert first["action"] == "ask"
    assert first["question_text"] == first["spoken_message"] == "Do you know the cream's name and how long you used it?"

    h.say(sid, auth, MAIN[1], reply_to=first["question_id"])
    second = h.tool(binding).json()
    assert second["action"] == "ask" and second["question_id"] != first["question_id"]

    h.say(sid, auth, MAIN[2], reply_to=second["question_id"])
    third = h.tool(binding)
    assert third.json() == {"action": "ready_to_confirm", "question_id": None, "question_text": None,
                            "spoken_message": SPOKEN_READY}
    for leaked in ("SYN-", "fictional encounter", "arranged a review", "case", "diagnos"):
        assert leaked not in third.text  # no case, action or diagnosis content to the voice model
    # The agent cannot confirm: state is ready, not confirmed.
    assert h.client.get(f"/v1/sessions/{sid}", headers=auth).json()["state"] == "ready_to_confirm"


def test_duplicate_tool_call_never_issues_a_second_question(h: Harness) -> None:
    sid, auth, binding = h.session()
    h.say(sid, auth, MAIN[0])
    first = h.tool(binding).json()
    again = h.tool(binding).json()
    assert again == first
    snapshot = h.client.get(f"/v1/sessions/{sid}", headers=auth).json()
    assert [q["question_id"] for q in snapshot["questions"]] == [first["question_id"]]


def test_agent_turns_do_not_count_as_patient_answers(h: Harness) -> None:
    sid, auth, binding = h.session()
    h.say(sid, auth, MAIN[0])
    first = h.tool(binding).json()
    h.say(sid, auth, first["question_text"], role="agent")  # the agent's own speech, persisted
    assert h.tool(binding).json() == first  # still waiting on the patient's answer


def test_model_supplied_body_is_ignored(h: Harness) -> None:
    sid, auth, binding = h.session()
    other_sid, other_auth, _ = h.session()
    h.say(other_sid, other_auth, MAIN[0])
    forged = h.tool(binding, {"session_id": other_sid, "transcript": MAIN[0]}).json()
    assert forged["action"] == "waiting_for_transcript"  # own session has nothing yet
    assert h.client.get(f"/v1/sessions/{other_sid}", headers=other_auth).json()["questions"] == []


def test_webhook_before_transcript_waits_then_answers() -> None:
    h = Harness(wait_seconds=2.0)
    sid, auth, binding = h.session()
    h.on_sleep = lambda: h.say(sid, auth, MAIN[0])  # transcript lands 0.2 s into the wait
    result = h.tool(binding).json()
    assert result["action"] == "ask"
    assert h.time <= 2.0


def test_webhook_wait_is_bounded_and_honest() -> None:
    h = Harness(wait_seconds=2.0)
    _, _, binding = h.session()
    result = h.tool(binding).json()
    assert result["action"] == "waiting_for_transcript" and result["question_id"] is None
    assert 2.0 <= h.time < 2.5  # bounded wait, then one honest technical message


def test_unprocessable_text_returns_safe_failure(h: Harness) -> None:
    sid, auth, binding = h.session()
    h.say(sid, auth, "Fictional words the S0 stub does not recognise.")
    res = h.tool(binding)
    assert res.status_code == 503
    body = res.json()
    assert body["error"]["code"] == "VOICE_ADVANCE_FAILED"
    assert "S0 stub" not in body["error"]["message"]  # internal detail not spoken to the user
