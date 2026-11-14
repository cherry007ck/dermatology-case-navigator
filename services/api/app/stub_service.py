"""S0 stub implementation of ``IntakeService`` — memory storage, no extraction.

What is real here: session tokens (HMAC-derived, stored hashed, constant-time
checks), patient-content revisions, stale-revision rejection, request-id
idempotency, confirmation at the current revision, clinician notes kept separate.

What is a stub: ``advance`` does not extract facts or rank cases. It replays the
shared contract example whose patient turn texts exactly equal this session's
active patient turns, remapping example turn IDs to this session's turn IDs. Any
other text returns a 503 ``EXTRACTION_UNAVAILABLE`` error rather than a
success-shaped empty brief. ``skip_question`` and ``correct_turn`` return
``STUB_NOT_IMPLEMENTED``. Zoro replaces this module in S1/S2.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.errors import ApiError
from app.fixtures import FixtureBundle, get_fixture_bundle
from app.models import (
    AdvanceRequest,
    AdvanceResult,
    AppendTurnsRequest,
    ClinicianNote,
    ClinicianNoteRequest,
    CollectionsResponse,
    ConfirmRequest,
    CorrectionRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    Modes,
    ReadinessResponse,
    SessionSnapshot,
    SkipQuestionRequest,
    Turn,
)
from app.repositories.memory import MemorySessionRepository, SessionRecord, StoredOperation

logger = logging.getLogger(__name__)

STUB_WARNINGS = [
    "Fictional demonstration cases — not published evidence.",
    "Fixture extraction and memory storage are demonstration modes.",
    "S0 stub service: results replay shared contract examples; no real extraction or ranking.",
]


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _input_hash(route: str, session_id: str, request: BaseModel) -> str:
    payload = json.dumps(
        {"route": route, "session_id": session_id, "body": request.model_dump(mode="json")},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _remap_ids(value: Any, mapping: dict[str, str]) -> Any:
    """Replace example turn IDs in evidence source_ids and answer_turn_ids."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "source_id" and value.get("source_type") == "patient_turn":
                out[key] = mapping.get(item, item)
            elif key == "answer_turn_ids":
                out[key] = [mapping.get(turn_id, turn_id) for turn_id in item]
            else:
                out[key] = _remap_ids(item, mapping)
        return out
    if isinstance(value, list):
        return [_remap_ids(item, mapping) for item in value]
    return value


class FixtureStubIntakeService:
    def __init__(
        self,
        settings: Settings | None = None,
        fixtures: FixtureBundle | None = None,
        repository: MemorySessionRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.fixtures = fixtures or get_fixture_bundle()
        self.repo = repository or MemorySessionRepository()
        secret = self.settings.session_token_secret
        if not secret:
            if not self.settings.is_development:
                raise RuntimeError("SESSION_TOKEN_SECRET must be set outside development")
            logger.warning("SESSION_TOKEN_SECRET unset; using a per-process development secret.")
            secret = secrets.token_urlsafe(32)
        self._token_key = secret.encode()

    # ------------------------------------------------------------------ helpers
    def _derive_token(self, session_id: str, creation_request_id: str) -> str:
        message = f"dcn.session-token.v1|{session_id}|{creation_request_id}".encode()
        return hmac.new(self._token_key, message, hashlib.sha256).hexdigest()

    def _modes(self) -> Modes:
        # Report what this implementation actually does, regardless of configuration.
        return Modes(storage="memory", extractor="fixture")

    def _snapshot(self, record: SessionRecord) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=record.session_id,
            revision=record.revision,
            state=record.state,
            confirmed_revision=record.confirmed_revision,
            turns=list(record.turns),
            facts=list(record.facts),
            questions=list(record.questions),
            search_history=list(record.search_history),
            brief=record.brief,
            clinician_notes=list(record.clinician_notes),
            warnings=list(STUB_WARNINGS),
            modes=self._modes(),
            collection=self.fixtures.collection,
        )

    def _authenticate(self, session_id: str, session_token: str) -> SessionRecord:
        record = self.repo.get(session_id)
        presented = _hash_token(session_token or "")
        expected = record.token_hash if record else _hash_token(secrets.token_hex(16))
        if record is None or not hmac.compare_digest(presented, expected):
            # Same response for unknown session and bad token: no existence oracle.
            raise ApiError(404, "SESSION_NOT_FOUND", "Session not found or not accessible.")
        return record

    @staticmethod
    def _check_revision(record: SessionRecord, expected: int, request_id: str) -> None:
        if expected != record.revision:
            raise ApiError(409, "REVISION_CONFLICT", "Reload the current session.", request_id=request_id)

    def _replay(self, record: SessionRecord, key: str, input_hash: str, request_id: str) -> str | None:
        stored = record.operations.get(key)
        if stored is None:
            return None
        if stored.input_hash != input_hash:
            raise ApiError(
                409, "IDEMPOTENCY_MISMATCH", "This request ID was already used with different content.",
                request_id=request_id,
            )
        return stored.response_json

    @staticmethod
    def _remember(record: SessionRecord, key: str, input_hash: str, response: BaseModel) -> None:
        record.operations[key] = StoredOperation(input_hash, response.model_dump_json())

    # ------------------------------------------------------------- frozen API
    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        if request.collection_id != self.fixtures.collection.collection_id:
            raise ApiError(404, "COLLECTION_NOT_FOUND", "Collection is not available.", request_id=request.request_id)
        input_hash = _input_hash("create_session", "", request)
        with self.repo.guard:
            existing = self.repo.find_creation(request.request_id)
        if existing:
            session_id, stored_hash = existing
            if stored_hash != input_hash:
                raise ApiError(409, "IDEMPOTENCY_MISMATCH", "This request ID was already used with different content.",
                               request_id=request.request_id)
            record = self.repo.get(session_id)
            assert record is not None
            return CreateSessionResponse(
                session_id=session_id,
                session_token=self._derive_token(session_id, request.request_id),
                snapshot=self._snapshot(record),
            )
        session_id = f"S-{uuid.uuid4()}"
        token = self._derive_token(session_id, request.request_id)
        record = SessionRecord(
            session_id=session_id,
            token_hash=_hash_token(token),
            collection_id=request.collection_id,
            creation_request_id=request.request_id,
        )
        self.repo.add(record, input_hash)
        return CreateSessionResponse(session_id=session_id, session_token=token, snapshot=self._snapshot(record))

    def get_session(self, session_id: str, session_token: str) -> SessionSnapshot:
        record = self._authenticate(session_id, session_token)
        with record.lock:
            return self._snapshot(record)

    def append_turns(self, session_id: str, session_token: str, request: AppendTurnsRequest) -> SessionSnapshot:
        record = self._authenticate(session_id, session_token)
        key = f"turns:{request.request_id}"
        input_hash = _input_hash("append_turns", session_id, request)
        with record.lock:
            if (replayed := self._replay(record, key, input_hash, request.request_id)) is not None:
                return SessionSnapshot.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            known = {turn.turn_id for turn in record.turns}
            if len({t.turn_id for t in request.turns}) != len(request.turns) or known & {t.turn_id for t in request.turns}:
                raise ApiError(409, "DUPLICATE_TURN_ID", "A turn with this ID already exists.",
                               request_id=request.request_id)
            now = _now()
            for item in request.turns:
                record.turns.append(
                    Turn(
                        turn_id=item.turn_id,
                        role=item.role,
                        origin=item.origin,
                        text=item.text,
                        reply_to_question_id=item.reply_to_question_id,
                        supersedes_turn_id=None,
                        sequence=len(record.turns) + 1,
                        created_at=now,
                    )
                )
            if any(item.role == "patient" for item in request.turns):
                # New patient content: one revision bump, confirmation invalidated.
                record.revision += 1
                record.confirmed_revision = None
                record.state = "intake"
            snapshot = self._snapshot(record)
            self._remember(record, key, input_hash, snapshot)
            return snapshot

    def advance(self, session_id: str, request: AdvanceRequest) -> AdvanceResult:
        record = self.repo.get(session_id)
        if record is None:
            raise ApiError(404, "SESSION_NOT_FOUND", "Session not found or not accessible.")
        key = f"advance:{request.request_id}"
        input_hash = _input_hash("advance", session_id, request)
        with record.lock:
            if (replayed := self._replay(record, key, input_hash, request.request_id)) is not None:
                return AdvanceResult.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            patient_turns = [t for t in record.turns if t.role == "patient" and t.supersedes_turn_id is None]
            texts = [t.text for t in patient_turns]
            example = next(
                (
                    ex for ex in self.fixtures.advance_examples.values()
                    if ex.snapshot.revision == record.revision
                    and [t.text for t in ex.snapshot.turns if t.role == "patient"] == texts
                ),
                None,
            )
            if example is None:
                raise ApiError(
                    503, "EXTRACTION_UNAVAILABLE",
                    "Extraction is not implemented yet. The S0 stub only replays the documented fictional demo phrases.",
                    request_id=request.request_id,
                )
            example_turn_ids = [t.turn_id for t in example.snapshot.turns if t.role == "patient"]
            mapping = dict(zip(example_turn_ids, [t.turn_id for t in patient_turns], strict=True))
            remapped = AdvanceResult.model_validate(_remap_ids(example.model_dump(mode="json"), mapping))
            record.facts = remapped.snapshot.facts
            record.questions = remapped.snapshot.questions
            record.search_history = remapped.snapshot.search_history
            record.brief = remapped.snapshot.brief
            record.state = remapped.snapshot.state
            result = AdvanceResult(snapshot=self._snapshot(record), action=remapped.action, question=remapped.question)
            self._remember(record, key, input_hash, result)
            return result

    def skip_question(self, session_id: str, session_token: str, request: SkipQuestionRequest) -> SessionSnapshot:
        self._authenticate(session_id, session_token)
        raise ApiError(503, "STUB_NOT_IMPLEMENTED", "Skipping questions is not implemented in the S0 stub.",
                       request_id=request.request_id)

    def correct_turn(self, session_id: str, session_token: str, request: CorrectionRequest) -> SessionSnapshot:
        self._authenticate(session_id, session_token)
        raise ApiError(503, "STUB_NOT_IMPLEMENTED", "Corrections are not implemented in the S0 stub.",
                       request_id=request.request_id)

    def confirm(self, session_id: str, session_token: str, request: ConfirmRequest) -> SessionSnapshot:
        record = self._authenticate(session_id, session_token)
        key = f"confirm:{request.request_id}"
        input_hash = _input_hash("confirm", session_id, request)
        with record.lock:
            if (replayed := self._replay(record, key, input_hash, request.request_id)) is not None:
                return SessionSnapshot.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            latest = record.search_history[-1] if record.search_history else None
            if (
                record.state != "ready_to_confirm"
                or latest is None
                or latest.patient_revision != record.revision
                or record.brief is None
                or record.brief.patient_revision != record.revision
            ):
                raise ApiError(409, "NOT_READY_TO_CONFIRM", "Review the latest statement before confirming.",
                               request_id=request.request_id)
            record.state = "confirmed"
            record.confirmed_revision = record.revision
            snapshot = self._snapshot(record)
            self._remember(record, key, input_hash, snapshot)
            return snapshot

    def add_clinician_note(self, session_id: str, session_token: str, request: ClinicianNoteRequest) -> ClinicianNote:
        record = self._authenticate(session_id, session_token)
        key = f"note:{request.request_id}"
        input_hash = _input_hash("add_clinician_note", session_id, request)
        with record.lock:
            if (replayed := self._replay(record, key, input_hash, request.request_id)) is not None:
                return ClinicianNote.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            note = ClinicianNote(
                note_id=f"N-{uuid.uuid4()}",
                patient_revision=record.revision,
                note_text=request.note_text,
                author_label=request.author_label,
                created_at=_now(),
            )
            record.clinician_notes.append(note)
            self._remember(record, key, input_hash, note)
            return note

    # ---------------------------------------------------------- read helpers
    def readiness(self) -> ReadinessResponse:
        mode = "synthetic" if self.settings.collection_mode != "published" else "published"
        loaded = self.fixtures.collection.case_count if mode == "synthetic" else 0
        # The stub can only serve memory storage and fixture extraction honestly.
        ready = self.settings.data_backend == "memory" and self.settings.extractor_mode == "fixture"
        return ReadinessResponse(storage="memory", extractor="fixture", collection_mode=mode,
                                 loaded_cases=loaded, ready=ready)

    def list_collections(self) -> CollectionsResponse:
        if self.settings.collection_mode == "published":
            return CollectionsResponse(collections=[])
        return CollectionsResponse(collections=[self.fixtures.collection])
