"""Live Exasol repository checks. Skipped unless DCN_LIVE_EXASOL=1 and credentials are configured.

    $env:DCN_LIVE_EXASOL="1"; python -m pytest tests/test_exasol_live.py

Uses a separate schema (EXASOL_TEST_SCHEMA, default DERMA_NAV_TEST) so app data is untouched.
Non-destructive: tables are created if missing and test rows are left in place (unique IDs).
CI never runs this; it has no Exasol credentials.
"""
from __future__ import annotations

import os
import uuid
from datetime import timedelta

import pytest

from app.config import get_settings
from app.extraction.rules import RuleCandidateProvider
from app.pipeline import IntakePipeline
from app.fixtures import get_fixture_bundle
from app.models import AdvanceRequest, AppendTurnsRequest, ClinicianNoteRequest, CreateSessionRequest, TurnInput
from app.repositories.base import CommitBatch, ConcurrentModification, OperationWrite

settings = get_settings()
pytestmark = pytest.mark.skipif(
    os.getenv("DCN_LIVE_EXASOL") != "1"
    or not (settings.exasol_dsn and settings.exasol_user and settings.exasol_password),
    reason="live Exasol check: set DCN_LIVE_EXASOL=1 and EXASOL_* in services/api/.env",
)
SCHEMA = os.getenv("EXASOL_TEST_SCHEMA", "DERMA_NAV_TEST")
SECRET = "live-test-session-secret-not-a-real-credential"
TEXT = "My hands have been itchy for weeks. I tried a cream, but it didn't help."


def new_repo():
    from app.repositories.exasol import ExasolEncounterRepository

    return ExasolEncounterRepository(settings.exasol_dsn, settings.exasol_user, settings.exasol_password, SCHEMA)


@pytest.fixture(scope="module")
def seeded():
    repo = new_repo()
    repo.initialize_schema()
    assert repo.missing_tables() == []
    bundle = get_fixture_bundle()
    assert repo.seed_collection(bundle.collection, bundle.cases) in {"inserted", "unchanged"}
    assert repo.seed_collection(bundle.collection, bundle.cases) == "unchanged"  # repeatable
    yield repo
    repo.close()


def service(repo):
    from app.service import EncounterService

    return EncounterService(settings, repo, IntakePipeline(RuleCandidateProvider()), token_secret=SECRET)


def test_seeded_cases_round_trip_with_integrity(seeded) -> None:
    bundle = get_fixture_bundle()
    stored = {c.collection_id: c for c in seeded.list_collections()}[bundle.collection.collection_id]
    assert stored == bundle.collection
    assert seeded.load_cases(bundle.collection.collection_id) == sorted(bundle.cases, key=lambda c: c.case_id)


def test_encounter_persists_across_connections(seeded) -> None:
    svc = service(seeded)
    created = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()),
                                                      collection_id="synthetic-demo-v1"))
    sid, token = created.session_id, created.session_token
    turn = TurnInput(turn_id=f"live-{uuid.uuid4()}", role="patient", origin="typed", text=TEXT,
                     reply_to_question_id=None)
    append = AppendTurnsRequest(request_id=str(uuid.uuid4()), expected_revision=0, turns=[turn])
    first = svc.append_turns(sid, token, append)
    assert svc.append_turns(sid, token, append) == first  # idempotent replay from Exasol
    result = svc.advance(sid, AdvanceRequest(request_id=str(uuid.uuid4()), expected_revision=1))
    note = svc.add_clinician_note(sid, token, ClinicianNoteRequest(
        request_id=str(uuid.uuid4()), expected_revision=1, note_text="Fictional note.", author_label="Demo"))

    fresh = new_repo()  # new connection: nothing cached in process
    try:
        snap = service(fresh).get_session(sid, token)
    finally:
        fresh.close()
    assert snap.modes.storage == "exasol"
    assert snap.revision == 1 and snap.turns == first.turns
    assert snap.search_history == result.snapshot.search_history and len(snap.search_history) == 1
    assert snap.brief == result.snapshot.brief and snap.facts == result.snapshot.facts
    assert snap.clinician_notes == [note]


def test_stale_write_version_is_rejected(seeded) -> None:
    svc = service(seeded)
    created = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()),
                                                      collection_id="synthetic-demo-v1"))
    record = seeded.load_session(created.session_id)
    stale = CommitBatch(record, record.write_version + 5, OperationWrite(f"probe:{uuid.uuid4()}", "0" * 64, "{}"))
    with pytest.raises(ConcurrentModification):
        seeded.commit(stale)
    assert seeded.load_session(created.session_id).write_version == record.write_version


def test_timestamps_round_trip_in_utc(seeded) -> None:
    svc = service(seeded)
    created = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()),
                                                      collection_id="synthetic-demo-v1"))
    record = seeded.load_session(created.session_id)
    assert record.expires_at - record.created_at == timedelta(hours=24)
    assert record.created_at.tzinfo is not None


def test_natural_wording_pipeline_computes_and_persists_comparisons(seeded) -> None:
    """S2 smoke: hesitant speech -> validated facts -> structured-v1 over cases read from Exasol."""
    svc = service(seeded)
    created = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()),
                                                      collection_id="synthetic-demo-v1"))
    sid, token, revision = created.session_id, created.session_token, 0
    lines = [
        "Um, hi. So my, uh, hands have been really itchy for a few weeks. I put some cream on, it didn't really help.",
        "Okay.",
        "Hmm, I can't remember what it was called. Maybe a couple of days?",
        "No, I haven't used any new products.",
    ]
    actions = []
    for n, text in enumerate(lines):
        turn = TurnInput(turn_id=f"live-s2-{uuid.uuid4()}", role="patient", origin="voice_transcript", text=text,
                         reply_to_question_id=None)
        revision = svc.append_turns(sid, token, AppendTurnsRequest(request_id=str(uuid.uuid4()),
                                                                   expected_revision=revision, turns=[turn])).revision
        actions.append(svc.advance(sid, AdvanceRequest(request_id=str(uuid.uuid4()), expected_revision=revision)).action)
    assert actions == ["ask", "ask", "ask", "ready_to_confirm"]

    fresh = new_repo()
    try:
        snap = service(fresh).get_session(sid, token)
    finally:
        fresh.close()
    assert snap.modes.storage == "exasol"
    assert [q.template_id for q in snap.questions] == ["cream_details_v1", "exposure_context_v1"]
    assert {(f.key, f.value, f.status) for f in snap.facts} >= {
        ("site", "hands", "reported"), ("symptom", "itching", "reported"), ("prior_treatment_name", None, "unknown"),
        ("exposure", "no_new_product", "reported")}
    ids = [s.search_id for s in snap.search_history]
    assert len(ids) == len(set(ids)) == 4
    last = snap.search_history[-1]
    assert last.ranked_case_ids == ["SYN-B"]
    assert {(c.case_id, c.change) for c in last.changes} == {("SYN-B", "moved"), ("SYN-A", "removed")}
    assert snap.brief.patient_revision == snap.revision
