"""Storage seam for the encounter service (S1).

Two implementations share this interface:

- ``app.repositories.memory.MemoryEncounterRepository``: tests and isolated development. Snapshots
  report ``modes.storage = "memory"``; nothing survives a restart.
- ``app.repositories.exasol.ExasolEncounterRepository``: live mode. Sessions, turns, operations,
  clinician notes, search versions and the seeded case collection live in Exasol.

Concurrency model (docs/02): the API runs one process. ``EncounterService`` serializes operations
per session with an in-process lock, and ``commit`` additionally checks ``write_version``
(optimistic concurrency) so a second writer can never silently overwrite a newer state. The
database's own uniqueness constraints are not relied on for correctness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

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

StorageMode = Literal["memory", "exasol"]


class StorageUnavailable(RuntimeError):
    """Storage could not be reached or a statement failed. Never carries SQL or credentials."""


class ConcurrentModification(RuntimeError):
    """``commit`` found a newer ``write_version`` than the one the operation started from."""


@dataclass
class StoredOperation:
    input_hash: str
    response_json: str


@dataclass
class EncounterRecord:
    session_id: str
    token_hash: str
    collection_id: str
    creation_request_id: str
    created_at: datetime
    expires_at: datetime
    revision: int = 0
    state: SessionState = "intake"
    confirmed_revision: int | None = None
    write_version: int = 0
    turns: list[Turn] = field(default_factory=list)
    facts: list[PatientFact] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    search_history: list[SearchVersion] = field(default_factory=list)
    brief: Brief | None = None
    clinician_notes: list[ClinicianNote] = field(default_factory=list)


@dataclass(frozen=True)
class OperationWrite:
    key: str
    input_hash: str
    response_json: str


@dataclass(frozen=True)
class CommitBatch:
    """Everything one successful operation writes, applied atomically by ``commit``.

    Turns, notes and search versions are append-only: existing rows are never updated or deleted.
    """

    record: EncounterRecord
    expected_write_version: int
    operation: OperationWrite
    new_turns: list[Turn] = field(default_factory=list)
    new_notes: list[ClinicianNote] = field(default_factory=list)
    new_searches: list[SearchVersion] = field(default_factory=list)


class EncounterRepository(Protocol):
    storage_mode: StorageMode

    def ping(self) -> None:
        """Raise ``StorageUnavailable`` if storage cannot answer a trivial query."""

    def list_collections(self) -> list[Collection]: ...

    def load_cases(self, collection_id: str) -> list[CaseRecord]: ...

    def find_creation(self, request_id: str) -> tuple[str, str] | None:
        """(session_id, input_hash) for an earlier create-session request ID."""

    def create_session(self, record: EncounterRecord, operation: OperationWrite) -> None: ...

    def load_session(self, session_id: str) -> EncounterRecord | None: ...

    def get_operation(self, session_id: str, key: str) -> StoredOperation | None: ...

    def commit(self, batch: CommitBatch) -> None:
        """Persist ``batch`` atomically and bump ``write_version``; ``ConcurrentModification`` if stale."""
