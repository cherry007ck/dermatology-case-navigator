"""``advance_intake`` webhook logic — Luffy's voice module.

Given a session resolved from an authenticated binding:

1. Wait at most ``WAIT_SECONDS`` for a newly persisted, active patient turn that has
   not yet been consumed by a voice advance (the browser persists transcripts through
   ``/turns``; the webhook may arrive first).
2. Derive the operation key from binding + that turn ID, so retries and duplicate tool
   calls can never issue a second question for the same answer.
3. Call the shared ``advance`` at the snapshot's revision. One re-read on a revision
   conflict (another turn landed in between).
4. Return only ``VoiceAdvanceResult``: action, question ID/text, spoken message. Never
   cases, diagnoses, actions, outcomes or clinician content.

The model supplies nothing: no session ID, transcript, facts or quotes.
Only the frozen ``IntakeService.get_session`` and ``advance`` are used; the session
bearer comes from the authenticated binding (see bindings.py), never from the model.
State (consumed turn, last result) is in memory per session; a restart only means the
next call re-reads the snapshot, and the service's idempotency keeps it safe.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.errors import ApiError
from app.intake_service import IntakeService
from app.models import AdvanceRequest, AdvanceResult, SessionSnapshot, Turn, VoiceAdvanceResult
from app.voice.bindings import ResolvedBinding

WAIT_SECONDS = 2.0
POLL_SECONDS = 0.2

SPOKEN_READY = (
    "Thank you. Please review your statement on the screen, and confirm it there only if it is correct."
)
SPOKEN_WAITING = "I'm still saving what you said. Please give me a moment."
SPOKEN_FAILED = "I couldn't process that just now. Please continue in the web app on your screen."


def _latest_patient_turn(snapshot: SessionSnapshot) -> Turn | None:
    superseded = {t.supersedes_turn_id for t in snapshot.turns if t.supersedes_turn_id}
    active = [t for t in snapshot.turns if t.role == "patient" and t.turn_id not in superseded]
    return max(active, key=lambda t: t.sequence) if active else None


def to_voice_result(result: AdvanceResult) -> VoiceAdvanceResult:
    if result.action == "ask" and result.question is not None:
        # Spoken exactly as approved by the backend; the agent adds nothing clinical.
        return VoiceAdvanceResult(
            action="ask", question_id=result.question.question_id,
            question_text=result.question.text, spoken_message=result.question.text,
        )
    if result.action == "ready_to_confirm":
        return VoiceAdvanceResult(action="ready_to_confirm", question_id=None, question_text=None,
                                  spoken_message=SPOKEN_READY)
    return VoiceAdvanceResult(action="waiting_for_transcript", question_id=None, question_text=None,
                              spoken_message=SPOKEN_WAITING)


WAITING = VoiceAdvanceResult(action="waiting_for_transcript", question_id=None, question_text=None,
                             spoken_message=SPOKEN_WAITING)


@dataclass
class _SessionVoiceState:
    consumed_turn_id: str | None = None
    last_result: VoiceAdvanceResult | None = None


class VoiceAdvancer:
    def __init__(
        self,
        *,
        wait_seconds: float = WAIT_SECONDS,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._wait = wait_seconds
        self._poll = poll_seconds
        self._sleep = sleep
        self._clock = clock
        self._states: dict[str, _SessionVoiceState] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def advance(self, service: IntakeService, binding: ResolvedBinding) -> VoiceAdvanceResult:
        session_id = binding.session_id

        def read() -> SessionSnapshot:
            return service.get_session(session_id, binding.session_token)

        with self._lock_for(session_id):  # duplicate concurrent tool calls are serialized
            state = self._states.setdefault(session_id, _SessionVoiceState())
            snapshot, turn = self._await_new_turn(read, state)
            if turn is None:
                # Nothing new: repeat the previous applicable result, or ask the agent to wait.
                return state.last_result or WAITING
            for attempt in range(2):
                op_key = hashlib.sha256(f"voice-advance|{binding.binding_hash}|{turn.turn_id}".encode()).hexdigest()[:32]
                try:
                    result = service.advance(session_id, AdvanceRequest(request_id=f"voice-{op_key}",
                                                                        expected_revision=snapshot.revision))
                except ApiError as exc:
                    if exc.code == "REVISION_CONFLICT" and attempt == 0:
                        snapshot = read()
                        turn = _latest_patient_turn(snapshot) or turn
                        continue
                    raise ApiError(exc.status_code if exc.status_code < 500 else 503, "VOICE_ADVANCE_FAILED",
                                   SPOKEN_FAILED, retryable=exc.retryable) from None
                voice = to_voice_result(result)
                state.consumed_turn_id = turn.turn_id
                state.last_result = voice
                return voice
            raise ApiError(409, "VOICE_ADVANCE_FAILED", SPOKEN_FAILED, retryable=True)

    def _await_new_turn(
        self, read: Callable[[], SessionSnapshot], state: _SessionVoiceState
    ) -> tuple[SessionSnapshot, Turn | None]:
        deadline = self._clock() + self._wait
        while True:
            snapshot = read()
            turn = _latest_patient_turn(snapshot)
            if turn is not None and turn.turn_id != state.consumed_turn_id:
                return snapshot, turn
            if self._clock() >= deadline:
                return snapshot, None
            self._sleep(self._poll)

    def forget(self, session_id: str) -> None:
        with self._guard:
            self._states.pop(session_id, None)


@lru_cache
def get_voice_advancer() -> VoiceAdvancer:
    return VoiceAdvancer()
