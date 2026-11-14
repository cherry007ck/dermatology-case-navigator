"""S1 ``IntakeService`` implementation over an ``EncounterRepository`` (memory or Exasol).

What is real: session tokens (HMAC-derived, stored hashed, constant-time checks), patient-content
revisions, stale-revision rejection, request-ID idempotency persisted with the encounter,
confirmation only at the current processed revision, clinician notes kept separate, append-only
turns/search versions/notes, and per-session serialization plus optimistic ``write_version`` checks.

S2: ``advance`` runs ``app.pipeline.IntakePipeline``: candidate extraction (Meta Model API, or the labelled
deterministic keyword rules in fixture mode), server validation against the patient's own words,
``structured-v1`` ranking over the cases stored for the encounter's collection, the two-question
policy and a template brief. A repeat ``advance`` at an already-processed revision returns the stored
result without re-extracting or issuing a new question.
Skip marks the pending question skipped (never a negative fact). Correction appends a superseding
turn and keeps the original. Both bump the patient revision and invalidate confirmation. In Exasol mode nothing falls back to
memory: a storage failure is a 503 ``STORAGE_UNAVAILABLE``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import TypeVar

from pydantic import BaseModel

from app.config import Settings
from app.errors import ApiError
from app.extraction.candidates import ExtractionUnavailable
from app.pipeline import IntakePipeline
from app.models import (
    AdvanceRequest,
    AdvanceResult,
    AppendTurnsRequest,
    ClinicianNote,
    ClinicianNoteRequest,
    Collection,
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
from app.repositories.base import (
    CommitBatch,
    ConcurrentModification,
    EncounterRecord,
    EncounterRepository,
    OperationWrite,
    StorageUnavailable,
)

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable)

SESSION_TTL = timedelta(hours=24)
FICTIONAL_WARNING = "Fictional demonstration cases — not published evidence."
PUBLISHED_WARNING = ("Published case reports: developer source-reviewed, not clinically reviewed. Cases are "
                     "comparison material for the doctor, not a diagnosis or treatment recommendation.")
FIXTURE_WARNING = (
    "Demo extraction: deterministic keyword rules (no language model); facts are checked against your exact words."
)
META_WARNING = (
    "Candidate facts are proposed by the Meta Model API and kept only when your exact words support them; not clinically validated."
)
RANKING_WARNING = ("Case comparison uses prototype structured rules (each search records its algorithm "
                   "version); not a validated clinical score.")
MEMORY_WARNING = "Development storage — not Exasol. Nothing survives an API restart."


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _input_hash(route: str, session_id: str, request: BaseModel) -> str:
    payload = json.dumps(
        {"route": route, "session_id": session_id, "body": request.model_dump(mode="json")}, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _storage_errors(method: F) -> F:
    """Map storage failures to the contract envelope without leaking driver details."""

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except StorageUnavailable:
            request = next((a for a in args if isinstance(a, BaseModel) and hasattr(a, "request_id")), None)
            raise ApiError(
                503, "STORAGE_UNAVAILABLE", "Encounter storage is temporarily unavailable. Retry shortly.",
                retryable=True, request_id=getattr(request, "request_id", None),
            ) from None

    return wrapper  # type: ignore[return-value]


class EncounterService:
    def __init__(
        self,
        settings: Settings,
        repository: EncounterRepository,
        extractor: IntakePipeline,
        *,
        token_secret: str | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repository
        self.extractor = extractor
        secret = token_secret if token_secret is not None else settings.session_token_secret
        if not secret:
            if not settings.is_development:
                raise RuntimeError("SESSION_TOKEN_SECRET must be set outside development")
            if repository.storage_mode == "exasol":
                # Persisted encounters would become unreachable after a restart with a random key.
                raise RuntimeError("SESSION_TOKEN_SECRET must be set when DATA_BACKEND=exasol")
            logger.warning("SESSION_TOKEN_SECRET unset; using a per-process development secret.")
            secret = secrets.token_urlsafe(32)
        self._token_key = secret.encode()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._create_guard = threading.Lock()
        self._collections: dict[str, Collection] = {}

    # ------------------------------------------------------------------ helpers
    def _lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def _derive_token(self, session_id: str, creation_request_id: str) -> str:
        message = f"dcn.session-token.v1|{session_id}|{creation_request_id}".encode()
        return hmac.new(self._token_key, message, hashlib.sha256).hexdigest()

    def _modes(self) -> Modes:
        return Modes(storage=self.repo.storage_mode, extractor=self.extractor.mode)

    def _visible_collections(self) -> list[Collection]:
        """Collections stored in the repository for the configured COLLECTION_MODE only."""
        collections = [c for c in self.repo.list_collections() if c.mode == self.settings.collection_mode]
        self._collections = {c.collection_id: c for c in collections}
        return collections

    def _collection(self, collection_id: str) -> Collection:
        if collection_id not in self._collections:
            self._visible_collections()
        collection = self._collections.get(collection_id)
        if collection is None:
            raise ApiError(503, "COLLECTION_UNAVAILABLE", "The encounter's case collection is not loaded.",
                           retryable=True)
        return collection

    def _warnings(self, collection: Collection) -> list[str]:
        source = FICTIONAL_WARNING if collection.mode == "synthetic" else PUBLISHED_WARNING
        warnings = [source, FIXTURE_WARNING if self.extractor.mode == "fixture" else META_WARNING,
                    RANKING_WARNING]
        if self.repo.storage_mode == "memory":
            warnings.append(MEMORY_WARNING)
        return warnings

    def _snapshot(self, record: EncounterRecord) -> SessionSnapshot:
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
            warnings=self._warnings(self._collection(record.collection_id)),
            modes=self._modes(),
            collection=self._collection(record.collection_id),
        )

    def _authenticate(self, session_id: str, session_token: str) -> EncounterRecord:
        record = self.repo.load_session(session_id)
        presented = _hash_token(session_token or "")
        expected = record.token_hash if record else _hash_token(secrets.token_hex(16))
        if record is None or not hmac.compare_digest(presented, expected) or _now() >= record.expires_at:
            # Same response for unknown, expired and wrong-token sessions: no existence oracle.
            raise ApiError(404, "SESSION_NOT_FOUND", "Session not found or not accessible.")
        return record

    @staticmethod
    def _check_revision(record: EncounterRecord, expected: int, request_id: str) -> None:
        if expected != record.revision:
            raise ApiError(409, "REVISION_CONFLICT", "Reload the current session.", request_id=request_id)

    def _replayed(self, session_id: str, key: str, input_hash: str, request_id: str) -> str | None:
        stored = self.repo.get_operation(session_id, key)
        if stored is None:
            return None
        if stored.input_hash != input_hash:
            raise ApiError(409, "IDEMPOTENCY_MISMATCH", "This request ID was already used with different content.",
                           request_id=request_id)
        return stored.response_json

    def _commit(self, batch: CommitBatch, request_id: str) -> None:
        try:
            self.repo.commit(batch)
        except ConcurrentModification:
            raise ApiError(409, "REVISION_CONFLICT", "Reload the current session.", request_id=request_id) from None

    # ------------------------------------------------------------- frozen API
    @_storage_errors
    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        if request.collection_id not in {c.collection_id for c in self._visible_collections()}:
            raise ApiError(404, "COLLECTION_NOT_FOUND", "Collection is not available.", request_id=request.request_id)
        input_hash = _input_hash("create_session", "", request)
        with self._create_guard:
            existing = self.repo.find_creation(request.request_id)
            if existing is None:
                now = _now()
                session_id = f"S-{uuid.uuid4()}"
                token = self._derive_token(session_id, request.request_id)
                record = EncounterRecord(
                    session_id=session_id,
                    token_hash=_hash_token(token),
                    collection_id=request.collection_id,
                    creation_request_id=request.request_id,
                    created_at=now,
                    expires_at=now + SESSION_TTL,
                )
                snapshot = self._snapshot(record)
                # The stored creation response is the snapshot only: the raw bearer is never persisted.
                self.repo.create_session(
                    record, OperationWrite("create", input_hash, snapshot.model_dump_json())
                )
                return CreateSessionResponse(session_id=session_id, session_token=token, snapshot=snapshot)
        session_id, stored_hash = existing
        if stored_hash != input_hash:
            raise ApiError(409, "IDEMPOTENCY_MISMATCH", "This request ID was already used with different content.",
                           request_id=request.request_id)
        original = self.repo.get_operation(session_id, "create")
        snapshot = (
            SessionSnapshot.model_validate_json(original.response_json)
            if original else self._snapshot(self._require(session_id))
        )
        return CreateSessionResponse(
            session_id=session_id,
            session_token=self._derive_token(session_id, request.request_id),
            snapshot=snapshot,
        )

    def _require(self, session_id: str) -> EncounterRecord:
        record = self.repo.load_session(session_id)
        if record is None:
            raise ApiError(404, "SESSION_NOT_FOUND", "Session not found or not accessible.")
        return record

    @_storage_errors
    def get_session(self, session_id: str, session_token: str) -> SessionSnapshot:
        return self._snapshot(self._authenticate(session_id, session_token))

    @_storage_errors
    def append_turns(self, session_id: str, session_token: str, request: AppendTurnsRequest) -> SessionSnapshot:
        key = f"turns:{request.request_id}"
        input_hash = _input_hash("append_turns", session_id, request)
        with self._lock(session_id):
            record = self._authenticate(session_id, session_token)
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
                return SessionSnapshot.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            known = {turn.turn_id for turn in record.turns}
            incoming = [t.turn_id for t in request.turns]
            if len(set(incoming)) != len(incoming) or known & set(incoming):
                raise ApiError(409, "DUPLICATE_TURN_ID", "A turn with this ID already exists.",
                               request_id=request.request_id)
            started_at, now = record.write_version, _now()
            new_turns = []
            for item in request.turns:
                turn = Turn(
                    turn_id=item.turn_id, role=item.role, origin=item.origin, text=item.text,
                    reply_to_question_id=item.reply_to_question_id, supersedes_turn_id=None,
                    sequence=len(record.turns) + 1, created_at=now,
                )
                record.turns.append(turn)
                new_turns.append(turn)
            if any(item.role == "patient" for item in request.turns):
                # New patient content: one revision bump, confirmation invalidated.
                record.revision += 1
                record.confirmed_revision = None
                record.state = "intake"
            snapshot = self._snapshot(record)
            self._commit(
                CommitBatch(record, started_at, OperationWrite(key, input_hash, snapshot.model_dump_json()),
                            new_turns=new_turns),
                request.request_id,
            )
            return snapshot

    @_storage_errors
    def advance(self, session_id: str, request: AdvanceRequest) -> AdvanceResult:
        # Callers authenticate first (session route: bearer; voice route: binding).
        key = f"advance:{request.request_id}"
        input_hash = _input_hash("advance", session_id, request)
        with self._lock(session_id):
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
                return AdvanceResult.model_validate_json(replayed)
            record = self._require(session_id)
            self._check_revision(record, request.expected_revision, request.request_id)
            started_at = record.write_version
            last = record.search_history[-1] if record.search_history else None
            if (last is not None and last.patient_revision == record.revision and record.brief is not None
                    and record.brief.patient_revision == record.revision):
                # Already processed at this revision (e.g. typed and voice both advancing): no re-extraction,
                # no new search version, never a second question for the same answer.
                pending = next((q for q in record.questions if q.status == "asked"), None)
                outcome = AdvanceResult(snapshot=self._snapshot(record),
                                        action="ask" if pending else "ready_to_confirm", question=pending)
            else:
                collection = self._collection(record.collection_id)
                cases = self.repo.load_cases(record.collection_id)
                if len(cases) != collection.case_count:
                    raise ApiError(503, "COLLECTION_UNAVAILABLE",
                                   "The case collection is not fully loaded in storage. Run the seed.",
                                   retryable=True, request_id=request.request_id)
                try:
                    result = self.extractor.process(
                        session_id=session_id, revision=record.revision, turns=record.turns,
                        questions=record.questions, search_history=record.search_history,
                        collection=collection, cases=cases, now=_now())
                except ExtractionUnavailable:
                    raise ApiError(503, "EXTRACTION_UNAVAILABLE",
                                   "Your words are saved, but extraction is temporarily unavailable. Retry shortly.",
                                   retryable=True, request_id=request.request_id) from None
                if result.rejected:
                    logger.info("advance: %d candidate fact(s) rejected by validation", len(result.rejected))
                new_searches = [result.new_search] if result.new_search else []
                if result.action != "waiting_for_transcript":
                    record.facts = result.facts
                    record.questions = result.questions
                    record.search_history = record.search_history + new_searches
                    record.brief = result.brief
                    record.state = result.state
                outcome = AdvanceResult(snapshot=self._snapshot(record), action=result.action,
                                        question=result.question)
                self._commit(
                    CommitBatch(record, started_at, OperationWrite(key, input_hash, outcome.model_dump_json()),
                                new_searches=new_searches),
                    request.request_id,
                )
                return outcome
            self._commit(CommitBatch(record, started_at, OperationWrite(key, input_hash, outcome.model_dump_json())),
                         request.request_id)
            return outcome

    @staticmethod
    def _patient_content_changed(record: EncounterRecord) -> None:
        """One revision bump; any confirmation is invalidated until the patient reviews again."""
        record.revision += 1
        record.confirmed_revision = None
        record.state = "intake"

    @_storage_errors
    def skip_question(self, session_id: str, session_token: str, request: SkipQuestionRequest) -> SessionSnapshot:
        """Mark the pending question skipped. Skipped is never a negative fact, and the question is not
        re-asked. The caller advances afterwards to recompute the brief at the new revision."""
        key = f"skip:{request.request_id}"
        input_hash = _input_hash("skip_question", session_id, request)
        with self._lock(session_id):
            record = self._authenticate(session_id, session_token)
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
                return SessionSnapshot.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            index = next((i for i, q in enumerate(record.questions) if q.question_id == request.question_id), None)
            if index is None:
                raise ApiError(404, "QUESTION_NOT_FOUND", "That question is not part of this encounter.",
                               request_id=request.request_id)
            if record.questions[index].status != "asked":
                raise ApiError(409, "QUESTION_NOT_PENDING", "Only the question currently asked can be skipped.",
                               request_id=request.request_id)
            started_at = record.write_version
            questions = list(record.questions)
            questions[index] = questions[index].model_copy(update={"status": "skipped", "answer_turn_ids": []})
            record.questions = questions
            self._patient_content_changed(record)
            snapshot = self._snapshot(record)
            self._commit(CommitBatch(record, started_at, OperationWrite(key, input_hash, snapshot.model_dump_json())),
                         request.request_id)
            return snapshot

    @_storage_errors
    def correct_turn(self, session_id: str, session_token: str, request: CorrectionRequest) -> SessionSnapshot:
        """Append a correction turn that supersedes a patient turn. The original text stays in history.
        Extraction then uses active turns only. The question budget is not reset."""
        key = f"correct:{request.request_id}"
        input_hash = _input_hash("correct_turn", session_id, request)
        with self._lock(session_id):
            record = self._authenticate(session_id, session_token)
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
                return SessionSnapshot.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            original = next((t for t in record.turns if t.turn_id == request.replaces_turn_id), None)
            if original is None:
                raise ApiError(404, "TURN_NOT_FOUND", "That statement is not part of this encounter.",
                               request_id=request.request_id)
            superseded = {t.supersedes_turn_id for t in record.turns if t.supersedes_turn_id}
            if original.role != "patient" or original.turn_id in superseded:
                raise ApiError(409, "TURN_NOT_CORRECTABLE",
                               "Only a current patient statement can be corrected. Reload to see the latest version.",
                               request_id=request.request_id)
            turn_id = f"corr-{hashlib.sha256(f'{session_id}|{request.request_id}'.encode()).hexdigest()[:24]}"
            if any(t.turn_id == turn_id for t in record.turns):
                raise ApiError(409, "DUPLICATE_TURN_ID", "A turn with this ID already exists.",
                               request_id=request.request_id)
            started_at = record.write_version
            turn = Turn(turn_id=turn_id, role="patient", origin="correction", text=request.replacement_text,
                        reply_to_question_id=original.reply_to_question_id, supersedes_turn_id=original.turn_id,
                        sequence=len(record.turns) + 1, created_at=_now())
            record.turns.append(turn)
            self._patient_content_changed(record)
            snapshot = self._snapshot(record)
            self._commit(
                CommitBatch(record, started_at, OperationWrite(key, input_hash, snapshot.model_dump_json()),
                            new_turns=[turn]),
                request.request_id,
            )
            return snapshot

    @_storage_errors
    def confirm(self, session_id: str, session_token: str, request: ConfirmRequest) -> SessionSnapshot:
        key = f"confirm:{request.request_id}"
        input_hash = _input_hash("confirm", session_id, request)
        with self._lock(session_id):
            record = self._authenticate(session_id, session_token)
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
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
            started_at = record.write_version
            record.state = "confirmed"
            record.confirmed_revision = record.revision
            snapshot = self._snapshot(record)
            self._commit(CommitBatch(record, started_at, OperationWrite(key, input_hash, snapshot.model_dump_json())),
                         request.request_id)
            return snapshot

    @_storage_errors
    def add_clinician_note(self, session_id: str, session_token: str, request: ClinicianNoteRequest) -> ClinicianNote:
        key = f"note:{request.request_id}"
        input_hash = _input_hash("add_clinician_note", session_id, request)
        with self._lock(session_id):
            record = self._authenticate(session_id, session_token)
            if (replayed := self._replayed(session_id, key, input_hash, request.request_id)) is not None:
                return ClinicianNote.model_validate_json(replayed)
            self._check_revision(record, request.expected_revision, request.request_id)
            note = ClinicianNote(
                note_id=f"N-{uuid.uuid4()}", patient_revision=record.revision, note_text=request.note_text,
                author_label=request.author_label, created_at=_now(),
            )
            started_at = record.write_version
            record.clinician_notes.append(note)
            self._commit(
                CommitBatch(record, started_at, OperationWrite(key, input_hash, note.model_dump_json()),
                            new_notes=[note]),
                request.request_id,
            )
            return note

    # ---------------------------------------------------------- read helpers
    def readiness(self) -> ReadinessResponse:
        """Actual modes. Storage problems make ``ready`` false instead of failing the probe."""
        try:
            self.repo.ping()
            collections = self._visible_collections()
            storage_ok = True
        except StorageUnavailable:
            collections, storage_ok = [], False
        loaded = sum(c.case_count for c in collections)
        ready = (
            storage_ok
            and loaded > 0
            and self.settings.data_backend == self.repo.storage_mode
            and self.settings.extractor_mode == self.extractor.mode
            and self.extractor.configured
        )
        return ReadinessResponse(
            storage=self.repo.storage_mode, extractor=self.extractor.mode,
            collection_mode="published" if self.settings.collection_mode == "published" else "synthetic",
            loaded_cases=loaded, ready=ready,
        )

    @_storage_errors
    def list_collections(self) -> CollectionsResponse:
        return CollectionsResponse(collections=self._visible_collections())
