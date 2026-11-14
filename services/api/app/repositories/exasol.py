"""Exasol implementation of ``EncounterRepository`` (live mode).

Tables (schema from ``EXASOL_SCHEMA``, default ``DERMA_NAV``; created by ``scripts.init_db``):

- COLLECTIONS, CASES, PASSAGES: the seeded case collection. Cases keep their validated JSON plus
  queryable IDs, kind, review status and a content hash; passages are stored as immutable rows.
- SESSIONS: one row per encounter with queryable session ID, revision, state, confirmation and
  ``WRITE_VERSION`` (optimistic concurrency). Current facts/questions/brief are validated JSON.
- TURNS, SEARCH_VERSIONS, CLINICIAN_NOTES: append-only rows; never updated or deleted.
- OPERATIONS: idempotency records (request key, input hash, original response).

docs/02 allows normalized case tables plus serialized validated JSON for encounter snapshots;
that is the simplification used here. Exasol constraints are not relied on for correctness:
the service serializes each session and ``commit`` checks ``WRITE_VERSION``.

The PAT goes in ``EXASOL_PASSWORD``: PyExasol 4.0.0 accepted a SaaS PAT as ``password=`` and
rejected it as ``access_token=`` in Zoro's S0 connectivity test.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar

# PyExasol 4 reports a usage event to Exasol on connect unless disabled. Opt out by default;
# set EXASOL_TELEMETRY_DISABLE explicitly in the environment to override this choice.
os.environ.setdefault("EXASOL_TELEMETRY_DISABLE", "1")

import pyexasol  # noqa: E402

from app.models import (  # noqa: E402
    Brief,
    CaseRecord,
    ClinicianNote,
    Collection,
    PatientFact,
    Question,
    SearchVersion,
    Turn,
)
from app.repositories.base import (  # noqa: E402
    CommitBatch,
    ConcurrentModification,
    EncounterRecord,
    OperationWrite,
    StorageUnavailable,
    StoredOperation,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")

_SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_IDLE_CHECK_SECONDS = 60.0

# Client-supplied IDs (turn and request IDs) are not length-limited by the v1 DTOs yet, so their
# columns are wide. Server-generated IDs are UUID-based and short.
_ID = "VARCHAR(2000) UTF8"
_JSON = "VARCHAR(2000000) UTF8"

SCHEMA_TABLES: dict[str, str] = {
    "COLLECTIONS": f"""
        COLLECTION_ID VARCHAR(128) UTF8 NOT NULL,
        COLLECTION_MODE VARCHAR(16) UTF8 NOT NULL,
        COLLECTION_VERSION VARCHAR(128) UTF8 NOT NULL,
        CASE_COUNT DECIMAL(9,0) NOT NULL,
        SOURCE_REVIEW_COUNT DECIMAL(9,0) NOT NULL,
        CLINICAL_REVIEWED BOOLEAN NOT NULL,
        SEEDED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (COLLECTION_ID)""",
    "CASES": f"""
        COLLECTION_ID VARCHAR(128) UTF8 NOT NULL,
        CASE_ID VARCHAR(128) UTF8 NOT NULL,
        SOURCE_KIND VARCHAR(16) UTF8 NOT NULL,
        CASE_TITLE VARCHAR(2000) UTF8 NOT NULL,
        SOURCE_VERSION VARCHAR(256) UTF8 NOT NULL,
        CASE_LICENSE VARCHAR(256) UTF8 NOT NULL,
        SOURCE_REVIEW_STATUS VARCHAR(32) UTF8 NOT NULL,
        CLINICAL_REVIEWED BOOLEAN NOT NULL,
        CASE_JSON {_JSON} NOT NULL,
        CASE_SHA256 CHAR(64) ASCII NOT NULL,
        PRIMARY KEY (COLLECTION_ID, CASE_ID)""",
    "PASSAGES": f"""
        COLLECTION_ID VARCHAR(128) UTF8 NOT NULL,
        CASE_ID VARCHAR(128) UTF8 NOT NULL,
        PASSAGE_ID VARCHAR(128) UTF8 NOT NULL,
        PASSAGE_SECTION VARCHAR(256) UTF8 NOT NULL,
        PASSAGE_LOCATOR VARCHAR(512) UTF8 NOT NULL,
        PASSAGE_TEXT {_JSON} NOT NULL,
        TEXT_SHA256 CHAR(64) ASCII NOT NULL,
        PRIMARY KEY (COLLECTION_ID, PASSAGE_ID)""",
    "SESSIONS": f"""
        SESSION_ID VARCHAR(64) UTF8 NOT NULL,
        TOKEN_HASH CHAR(64) ASCII NOT NULL,
        COLLECTION_ID VARCHAR(128) UTF8 NOT NULL,
        CREATION_REQUEST_ID {_ID} NOT NULL,
        CREATION_INPUT_HASH CHAR(64) ASCII NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        EXPIRES_AT TIMESTAMP NOT NULL,
        PATIENT_REVISION DECIMAL(9,0) NOT NULL,
        SESSION_STATE VARCHAR(32) UTF8 NOT NULL,
        CONFIRMED_REVISION DECIMAL(9,0),
        WRITE_VERSION DECIMAL(18,0) NOT NULL,
        FACTS_JSON {_JSON} NOT NULL,
        QUESTIONS_JSON {_JSON} NOT NULL,
        BRIEF_JSON {_JSON},
        UPDATED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (SESSION_ID)""",
    "TURNS": f"""
        SESSION_ID VARCHAR(64) UTF8 NOT NULL,
        TURN_ID {_ID} NOT NULL,
        SEQ_NO DECIMAL(9,0) NOT NULL,
        TURN_ROLE VARCHAR(16) UTF8 NOT NULL,
        TURN_ORIGIN VARCHAR(32) UTF8 NOT NULL,
        TURN_TEXT {_JSON} NOT NULL,
        REPLY_TO_QUESTION_ID {_ID},
        SUPERSEDES_TURN_ID {_ID},
        CREATED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (SESSION_ID, TURN_ID)""",
    "OPERATIONS": f"""
        SESSION_ID VARCHAR(64) UTF8 NOT NULL,
        OP_KEY {_ID} NOT NULL,
        INPUT_HASH CHAR(64) ASCII NOT NULL,
        RESPONSE_JSON {_JSON} NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (SESSION_ID, OP_KEY)""",
    "SEARCH_VERSIONS": f"""
        SESSION_ID VARCHAR(64) UTF8 NOT NULL,
        SEARCH_ID VARCHAR(256) UTF8 NOT NULL,
        SEQ_NO DECIMAL(9,0) NOT NULL,
        PATIENT_REVISION DECIMAL(9,0) NOT NULL,
        ALGORITHM_VERSION VARCHAR(128) UTF8 NOT NULL,
        COLLECTION_VERSION VARCHAR(128) UTF8 NOT NULL,
        SEARCH_JSON {_JSON} NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (SESSION_ID, SEARCH_ID)""",
    "CLINICIAN_NOTES": f"""
        SESSION_ID VARCHAR(64) UTF8 NOT NULL,
        NOTE_ID VARCHAR(64) UTF8 NOT NULL,
        SEQ_NO DECIMAL(9,0) NOT NULL,
        PATIENT_REVISION DECIMAL(9,0) NOT NULL,
        AUTHOR_LABEL VARCHAR(512) UTF8 NOT NULL,
        NOTE_TEXT {_JSON} NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        PRIMARY KEY (SESSION_ID, NOTE_ID)""",
}


def _ts(value: datetime) -> str:
    """UTC timestamp literal for a TIMESTAMP column (second precision, as the service produces)."""
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return datetime.fromisoformat(str(value)).replace(tzinfo=UTC, microsecond=0)


def _int_or_null(value: int | None) -> str:
    """Literal for a nullable integer column; used with the raw ``!r`` conversion."""
    return "NULL" if value is None else str(int(value))


def _bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _json_list(items: list) -> str:
    return "[" + ",".join(item.model_dump_json() for item in items) + "]"


class ExasolEncounterRepository:
    """Single-connection repository. All database access is serialized by one lock.

    The prototype API runs one process (docs/03), so one connection is enough. A failed
    statement rolls back the open transaction; a broken connection is replaced once.
    """

    storage_mode = "exasol"

    def __init__(
        self,
        dsn: str,
        user: str,
        password: str,
        schema: str = "DERMA_NAV",
        *,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        if not (dsn and user and password):
            raise StorageUnavailable(
                "DATA_BACKEND=exasol needs EXASOL_DSN, EXASOL_USER and EXASOL_PASSWORD; refusing to use memory."
            )
        if not _SCHEMA_NAME.match(schema):
            raise ValueError("EXASOL_SCHEMA must be a plain identifier")
        self._dsn, self._user, self._password = dsn, user, password
        self.schema = schema.upper()
        self._connect = connect or pyexasol.connect
        self._conn: Any = None
        self._last_used = 0.0
        self._lock = threading.RLock()

    # ------------------------------------------------------------- connection
    def _open(self) -> Any:
        try:
            return self._connect(
                dsn=self._dsn,
                user=self._user,
                password=self._password,  # SaaS PAT; see module docstring
                encryption=True,  # TLS with certificate verification (PyExasol >= 1.0 default)
                autocommit=False,
                fetch_dict=True,
                verbose_error=False,
                connection_timeout=10,
                socket_timeout=30,
                client_name="dermatology-case-navigator-api",
            )
        except Exception as exc:
            # Log only the exception class: driver messages can include host or user details.
            logger.warning("Exasol connection failed (%s)", type(exc).__name__)
            raise StorageUnavailable("Exasol is not reachable.") from None

    def _connection(self) -> Any:
        """Open connection, re-checked after an idle period (SaaS clusters drop idle sockets)."""
        if self._conn is not None and not getattr(self._conn, "is_closed", False):
            if time.monotonic() - self._last_used < _IDLE_CHECK_SECONDS:
                return self._conn
            try:
                self._conn.execute("SELECT 1").fetchval()
                return self._conn
            except Exception:
                logger.warning("Idle Exasol connection was dropped; reconnecting")
                self._discard()
        self._conn = self._open()
        return self._conn

    @contextmanager
    def _transaction(self) -> Iterator[Any]:
        """Run statements in one transaction: commit on success, roll back on any error.

        Errors become ``StorageUnavailable`` without driver text (which can contain SQL or
        connection details). A connection lost mid-transaction is discarded; nothing was
        committed, so the client may retry the same request ID.
        """
        with self._lock:
            conn = self._connection()
            try:
                yield conn
                conn.commit()
            except ConcurrentModification:
                self._rollback()
                raise
            except StorageUnavailable:
                self._rollback()
                raise
            except pyexasol.ExaCommunicationError:
                self._discard()
                logger.warning("Exasol connection lost during a transaction")
                raise StorageUnavailable("Exasol connection was lost. Retry the request.") from None
            except Exception as exc:
                self._rollback()
                logger.warning("Exasol statement failed (%s)", type(exc).__name__)
                raise StorageUnavailable("An Exasol statement failed.") from None
            finally:
                self._last_used = time.monotonic()

    def _rollback(self) -> None:
        try:
            if self._conn is not None:
                self._conn.rollback()
        except Exception:
            self._discard()

    def _discard(self) -> None:
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def close(self) -> None:
        with self._lock:
            self._discard()

    def _t(self, table: str) -> str:
        return f'"{self.schema}"."{table}"'

    def _rows(self, conn: Any, sql: str, params: dict | None = None) -> list[dict]:
        return list(conn.execute(sql, params or {}).fetchall())

    # ------------------------------------------------------------- schema/seed
    def initialize_schema(self) -> list[str]:
        """Create the schema and missing tables. Never drops or alters existing objects."""
        created: list[str] = []
        with self._transaction() as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
            existing = {
                row["TABLE_NAME"]
                for row in self._rows(
                    conn,
                    "SELECT TABLE_NAME FROM SYS.EXA_ALL_TABLES WHERE TABLE_SCHEMA = {s}",
                    {"s": self.schema},
                )
            }
            for name, columns in SCHEMA_TABLES.items():
                if name not in existing:
                    conn.execute(f"CREATE TABLE IF NOT EXISTS {self._t(name)} ({columns})")
                    created.append(name)
        return created

    def missing_tables(self) -> list[str]:
        with self._transaction() as conn:
            existing = {
                row["TABLE_NAME"]
                for row in self._rows(
                    conn,
                    "SELECT TABLE_NAME FROM SYS.EXA_ALL_TABLES WHERE TABLE_SCHEMA = {s}",
                    {"s": self.schema},
                )
            }
        return [name for name in SCHEMA_TABLES if name not in existing]

    def seed_collection(self, collection: Collection, cases: list[CaseRecord]) -> str:
        """Insert a validated collection once. Returns 'inserted' or 'unchanged'.

        Non-destructive: an existing collection ID with a different version is refused rather than
        overwritten; publish a changed collection under a new collection ID.
        """
        with self._transaction() as conn:
            rows = self._rows(
                conn,
                f"SELECT COLLECTION_VERSION, CASE_COUNT FROM {self._t('COLLECTIONS')} WHERE COLLECTION_ID = {{c}}",
                {"c": collection.collection_id},
            )
            if rows:
                if rows[0]["COLLECTION_VERSION"] != collection.version:
                    raise ValueError(
                        f"Collection {collection.collection_id} already exists with a different version; "
                        "refusing to overwrite. Use a new collection ID."
                    )
                stored = int(self._rows(
                    conn,
                    f"SELECT COUNT(*) AS N FROM {self._t('CASES')} WHERE COLLECTION_ID = {{c}}",
                    {"c": collection.collection_id},
                )[0]["N"])
                if stored != collection.case_count:
                    raise ValueError(f"Collection {collection.collection_id} is incomplete in Exasol ({stored} cases).")
                return "unchanged"
            for case in cases:
                case_json = case.model_dump_json()
                conn.execute(
                    f"INSERT INTO {self._t('CASES')} VALUES ({{c}}, {{id}}, {{kind}}, {{title}}, {{ver}}, "
                    f"{{lic}}, {{rs}}, {{cr!r}}, {{js}}, {{sha}})",
                    {
                        "c": collection.collection_id, "id": case.case_id, "kind": case.source_kind,
                        "title": case.title, "ver": case.source_version, "lic": case.license,
                        "rs": case.source_review.status, "cr": _bool(case.clinical_reviewed),
                        "js": case_json, "sha": _sha(case_json),
                    },
                )
                for passage in case.passages:
                    conn.execute(
                        f"INSERT INTO {self._t('PASSAGES')} VALUES ({{c}}, {{case}}, {{pid}}, {{sec}}, {{loc}}, "
                        f"{{txt}}, {{sha}})",
                        {
                            "c": collection.collection_id, "case": case.case_id, "pid": passage.passage_id,
                            "sec": passage.section, "loc": passage.locator, "txt": passage.text,
                            "sha": passage.sha256,
                        },
                    )
            # The collection row is written last: its presence marks a complete seed.
            conn.execute(
                f"INSERT INTO {self._t('COLLECTIONS')} VALUES ({{c}}, {{mode}}, {{ver}}, {{n!d}}, {{rc!d}}, "
                f"{{cr!r}}, TIMESTAMP {{at}})",
                {
                    "c": collection.collection_id, "mode": collection.mode, "ver": collection.version,
                    "n": collection.case_count, "rc": collection.source_review_count,
                    "cr": _bool(collection.clinical_reviewed), "at": _ts(datetime.now(UTC)),
                },
            )
        return "inserted"

    # -------------------------------------------------------- EncounterRepository
    def ping(self) -> None:
        with self._transaction() as conn:
            conn.execute("SELECT 1").fetchval()

    def list_collections(self) -> list[Collection]:
        with self._transaction() as conn:
            rows = self._rows(conn, f"SELECT * FROM {self._t('COLLECTIONS')} ORDER BY COLLECTION_ID")
        return [
            Collection(
                collection_id=row["COLLECTION_ID"],
                mode=row["COLLECTION_MODE"],
                version=row["COLLECTION_VERSION"],
                case_count=int(row["CASE_COUNT"]),
                source_review_count=int(row["SOURCE_REVIEW_COUNT"]),
                clinical_reviewed=bool(row["CLINICAL_REVIEWED"]),
            )
            for row in rows
        ]

    def load_cases(self, collection_id: str) -> list[CaseRecord]:
        with self._transaction() as conn:
            rows = self._rows(
                conn,
                f"SELECT CASE_ID, CASE_JSON, CASE_SHA256 FROM {self._t('CASES')} "
                "WHERE COLLECTION_ID = {c} ORDER BY CASE_ID",
                {"c": collection_id},
            )
        cases = []
        for row in rows:
            if _sha(row["CASE_JSON"]) != row["CASE_SHA256"]:
                raise StorageUnavailable(f"Stored case {row['CASE_ID']} failed its integrity check.")
            cases.append(CaseRecord.model_validate_json(row["CASE_JSON"]))
        return cases

    def find_creation(self, request_id: str) -> tuple[str, str] | None:
        with self._transaction() as conn:
            rows = self._rows(
                conn,
                f"SELECT SESSION_ID, CREATION_INPUT_HASH FROM {self._t('SESSIONS')} WHERE CREATION_REQUEST_ID = {{r}}",
                {"r": request_id},
            )
        return (rows[0]["SESSION_ID"], rows[0]["CREATION_INPUT_HASH"]) if rows else None

    def create_session(self, record: EncounterRecord, operation: OperationWrite) -> None:
        now = _ts(record.created_at)
        with self._transaction() as conn:
            conn.execute(
                f"INSERT INTO {self._t('SESSIONS')} VALUES ({{sid}}, {{th}}, {{c}}, {{rid}}, {{ih}}, TIMESTAMP {{ca}}, TIMESTAMP {{ea}}, "
                f"{{rev!d}}, {{st}}, {{cr!r}}, {{wv!d}}, {{facts}}, {{qs}}, {{brief}}, TIMESTAMP {{ua}})",
                {
                    "sid": record.session_id, "th": record.token_hash, "c": record.collection_id,
                    "rid": record.creation_request_id, "ih": operation.input_hash, "ca": now,
                    "ea": _ts(record.expires_at), "rev": record.revision, "st": record.state,
                    "cr": _int_or_null(record.confirmed_revision), "wv": record.write_version,
                    "facts": _json_list(record.facts), "qs": _json_list(record.questions),
                    "brief": record.brief.model_dump_json() if record.brief else None, "ua": now,
                },
            )
            self._insert_operation(conn, record.session_id, operation)

    def load_session(self, session_id: str) -> EncounterRecord | None:
        with self._transaction() as conn:
            rows = self._rows(conn, f"SELECT * FROM {self._t('SESSIONS')} WHERE SESSION_ID = {{s}}", {"s": session_id})
            if not rows:
                return None
            row = rows[0]
            turns = self._rows(
                conn, f"SELECT * FROM {self._t('TURNS')} WHERE SESSION_ID = {{s}} ORDER BY SEQ_NO", {"s": session_id}
            )
            searches = self._rows(
                conn,
                f"SELECT SEARCH_JSON FROM {self._t('SEARCH_VERSIONS')} WHERE SESSION_ID = {{s}} ORDER BY SEQ_NO",
                {"s": session_id},
            )
            notes = self._rows(
                conn,
                f"SELECT * FROM {self._t('CLINICIAN_NOTES')} WHERE SESSION_ID = {{s}} ORDER BY SEQ_NO",
                {"s": session_id},
            )
        return EncounterRecord(
            session_id=row["SESSION_ID"],
            token_hash=row["TOKEN_HASH"],
            collection_id=row["COLLECTION_ID"],
            creation_request_id=row["CREATION_REQUEST_ID"],
            created_at=_dt(row["CREATED_AT"]),
            expires_at=_dt(row["EXPIRES_AT"]),
            revision=int(row["PATIENT_REVISION"]),
            state=row["SESSION_STATE"],
            confirmed_revision=None if row["CONFIRMED_REVISION"] is None else int(row["CONFIRMED_REVISION"]),
            write_version=int(row["WRITE_VERSION"]),
            turns=[
                Turn(
                    turn_id=t["TURN_ID"], role=t["TURN_ROLE"], origin=t["TURN_ORIGIN"], text=t["TURN_TEXT"],
                    reply_to_question_id=t["REPLY_TO_QUESTION_ID"], supersedes_turn_id=t["SUPERSEDES_TURN_ID"],
                    sequence=int(t["SEQ_NO"]), created_at=_dt(t["CREATED_AT"]),
                )
                for t in turns
            ],
            facts=[PatientFact.model_validate(f) for f in _parse_list(row["FACTS_JSON"])],
            questions=[Question.model_validate(q) for q in _parse_list(row["QUESTIONS_JSON"])],
            search_history=[SearchVersion.model_validate_json(s["SEARCH_JSON"]) for s in searches],
            brief=Brief.model_validate_json(row["BRIEF_JSON"]) if row["BRIEF_JSON"] else None,
            clinician_notes=[
                ClinicianNote(
                    note_id=n["NOTE_ID"], patient_revision=int(n["PATIENT_REVISION"]), note_text=n["NOTE_TEXT"],
                    author_label=n["AUTHOR_LABEL"], created_at=_dt(n["CREATED_AT"]),
                )
                for n in notes
            ],
        )

    def get_operation(self, session_id: str, key: str) -> StoredOperation | None:
        with self._transaction() as conn:
            rows = self._rows(
                conn,
                f"SELECT INPUT_HASH, RESPONSE_JSON FROM {self._t('OPERATIONS')} "
                "WHERE SESSION_ID = {s} AND OP_KEY = {k}",
                {"s": session_id, "k": key},
            )
        return StoredOperation(rows[0]["INPUT_HASH"], rows[0]["RESPONSE_JSON"]) if rows else None

    def commit(self, batch: CommitBatch) -> None:
        record = batch.record
        now = _ts(datetime.now(UTC))
        with self._transaction() as conn:
            updated = conn.execute(
                f"UPDATE {self._t('SESSIONS')} SET PATIENT_REVISION = {{rev!d}}, SESSION_STATE = {{st}}, "
                f"CONFIRMED_REVISION = {{cr!r}}, FACTS_JSON = {{facts}}, QUESTIONS_JSON = {{qs}}, "
                f"BRIEF_JSON = {{brief}}, WRITE_VERSION = WRITE_VERSION + 1, UPDATED_AT = TIMESTAMP {{ua}} "
                f"WHERE SESSION_ID = {{sid}} AND WRITE_VERSION = {{wv!d}}",
                {
                    "rev": record.revision, "st": record.state, "cr": _int_or_null(record.confirmed_revision),
                    "facts": _json_list(record.facts), "qs": _json_list(record.questions),
                    "brief": record.brief.model_dump_json() if record.brief else None, "ua": now,
                    "sid": record.session_id, "wv": batch.expected_write_version,
                },
            ).rowcount()
            if updated != 1:
                raise ConcurrentModification(record.session_id)
            for turn in batch.new_turns:
                conn.execute(
                    f"INSERT INTO {self._t('TURNS')} VALUES ({{sid}}, {{tid}}, {{seq!d}}, {{role}}, {{origin}}, "
                    f"{{txt}}, {{reply}}, {{sup}}, TIMESTAMP {{ca}})",
                    {
                        "sid": record.session_id, "tid": turn.turn_id, "seq": turn.sequence, "role": turn.role,
                        "origin": turn.origin, "txt": turn.text, "reply": turn.reply_to_question_id,
                        "sup": turn.supersedes_turn_id, "ca": _ts(turn.created_at),
                    },
                )
            first_search = len(record.search_history) - len(batch.new_searches)
            for offset, search in enumerate(batch.new_searches):
                conn.execute(
                    f"INSERT INTO {self._t('SEARCH_VERSIONS')} VALUES ({{sid}}, {{id}}, {{seq!d}}, {{rev!d}}, "
                    f"{{alg}}, {{cv}}, {{js}}, TIMESTAMP {{ca}})",
                    {
                        "sid": record.session_id, "id": search.search_id, "seq": first_search + offset + 1,
                        "rev": search.patient_revision, "alg": search.algorithm_version,
                        "cv": search.collection_version, "js": search.model_dump_json(),
                        "ca": _ts(search.created_at),
                    },
                )
            first_note = len(record.clinician_notes) - len(batch.new_notes)
            for offset, note in enumerate(batch.new_notes):
                conn.execute(
                    f"INSERT INTO {self._t('CLINICIAN_NOTES')} VALUES ({{sid}}, {{id}}, {{seq!d}}, {{rev!d}}, "
                    f"{{author}}, {{txt}}, TIMESTAMP {{ca}})",
                    {
                        "sid": record.session_id, "id": note.note_id, "seq": first_note + offset + 1,
                        "rev": note.patient_revision, "author": note.author_label, "txt": note.note_text,
                        "ca": _ts(note.created_at),
                    },
                )
            self._insert_operation(conn, record.session_id, batch.operation)
        record.write_version = batch.expected_write_version + 1

    def _insert_operation(self, conn: Any, session_id: str, op: OperationWrite) -> None:
        conn.execute(
            f"INSERT INTO {self._t('OPERATIONS')} VALUES ({{sid}}, {{k}}, {{ih}}, {{js}}, TIMESTAMP {{ca}})",
            {"sid": session_id, "k": op.key, "ih": op.input_hash, "js": op.response_json,
             "ca": _ts(datetime.now(UTC))},
        )


def _parse_list(raw: str) -> list:
    import json

    value = json.loads(raw)
    if not isinstance(value, list):
        raise StorageUnavailable("Stored encounter JSON is malformed.")
    return value
