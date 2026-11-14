"""In-memory stores for development and CI.

``MemorySessionRepository`` backs the S0 stub (kept only because the voice tests construct it).
``MemoryEncounterRepository`` backs the S1 ``EncounterService`` in memory mode.

Not Exasol. Everything is lost when the process restarts. Snapshots carry
``modes.storage = "memory"`` and the UI shows "Development storage — not Exasol."
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field

from app.models import (
    Brief,
    CaseRecord,
    ClinicianNote,
    Collection,
    PatientFact,
    Question,
    SearchVersion,
    SessionState,
    Turn,
)
from app.repositories.base import (
    CommitBatch,
    ConcurrentModification,
    EncounterRecord,
    OperationWrite,
)
from app.repositories.base import StoredOperation as EncounterOperation


@dataclass
class StoredOperation:
    input_hash: str
    response_json: str


@dataclass
class SessionRecord:
    session_id: str
    token_hash: str
    collection_id: str
    creation_request_id: str
    revision: int = 0
    state: SessionState = "intake"
    confirmed_revision: int | None = None
    turns: list[Turn] = field(default_factory=list)
    facts: list[PatientFact] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    search_history: list[SearchVersion] = field(default_factory=list)
    brief: Brief | None = None
    clinician_notes: list[ClinicianNote] = field(default_factory=list)
    operations: dict[str, StoredOperation] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class MemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._creation_requests: dict[str, tuple[str, str]] = {}  # request_id -> (session_id, input_hash)
        self._guard = threading.Lock()

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def find_creation(self, request_id: str) -> tuple[str, str] | None:
        return self._creation_requests.get(request_id)

    def add(self, record: SessionRecord, input_hash: str) -> None:
        with self._guard:
            self._sessions[record.session_id] = record
            self._creation_requests[record.creation_request_id] = (record.session_id, input_hash)

    @property
    def guard(self) -> threading.Lock:
        return self._guard


# ---------------------------------------------------------------------------
# S1 encounter repository (used by app.service.EncounterService)
# ---------------------------------------------------------------------------


class MemoryEncounterRepository:
    """Memory implementation of ``app.repositories.base.EncounterRepository``.

    Records are deep-copied on the way in and out so the service cannot change stored state
    without ``commit``; this keeps memory behaviour equivalent to the Exasol repository.
    """

    storage_mode = "memory"

    def __init__(self, collection: Collection, cases: list[CaseRecord]) -> None:
        self._collection = collection
        self._cases = list(cases)
        self._sessions: dict[str, EncounterRecord] = {}
        self._creations: dict[str, tuple[str, str]] = {}
        self._operations: dict[tuple[str, str], EncounterOperation] = {}
        self._lock = threading.Lock()

    def ping(self) -> None:
        return None

    def list_collections(self) -> list[Collection]:
        return [self._collection]

    def load_cases(self, collection_id: str) -> list[CaseRecord]:
        return [c for c in self._cases if c.collection_id == collection_id]

    def find_creation(self, request_id: str) -> tuple[str, str] | None:
        with self._lock:
            return self._creations.get(request_id)

    def create_session(self, record: EncounterRecord, operation: OperationWrite) -> None:
        with self._lock:
            self._sessions[record.session_id] = copy.deepcopy(record)
            self._creations[record.creation_request_id] = (record.session_id, operation.input_hash)
            self._operations[(record.session_id, operation.key)] = EncounterOperation(
                operation.input_hash, operation.response_json
            )

    def load_session(self, session_id: str) -> EncounterRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            return copy.deepcopy(record) if record else None

    def get_operation(self, session_id: str, key: str) -> EncounterOperation | None:
        with self._lock:
            return self._operations.get((session_id, key))

    def commit(self, batch: CommitBatch) -> None:
        with self._lock:
            current = self._sessions.get(batch.record.session_id)
            if current is None or current.write_version != batch.expected_write_version:
                raise ConcurrentModification(batch.record.session_id)
            stored = copy.deepcopy(batch.record)
            stored.write_version = batch.expected_write_version + 1
            self._sessions[stored.session_id] = stored
            op = batch.operation
            self._operations[(stored.session_id, op.key)] = EncounterOperation(op.input_hash, op.response_json)
        batch.record.write_version = batch.expected_write_version + 1
