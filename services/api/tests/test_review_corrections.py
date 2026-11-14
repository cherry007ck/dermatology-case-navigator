"""Named product use, live correction and skip (memory repository; same EncounterRepository contract as Exasol)."""
from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from app.config import REPO_ROOT, get_settings
from app.errors import ApiError
from app.evidence.validate import validate
from app.extraction.candidates import Candidate, ExtractionInput
from app.extraction.rules import RuleCandidateProvider
from app.extraction.vocabulary import product_mentions
from app.fixtures import get_fixture_bundle
from app.models import (AdvanceRequest, AppendTurnsRequest, ConfirmRequest, CorrectionRequest, CreateSessionRequest,
                        SkipQuestionRequest, Turn, TurnInput)
from app.pipeline import IntakePipeline
from app.published import build_collection, read_records
from app.repositories.memory import MemoryEncounterRepository
from app.service import EncounterService

SYNTH = get_fixture_bundle()
PUB = "published-derm-v1"


def rid() -> str:
    return str(uuid.uuid4())


class Encounter:
    def __init__(self, published: bool = False) -> None:
        if published:
            raw = read_records(REPO_ROOT / "data" / "published" / "reviewed")
            collection, cases = build_collection(raw, PUB)
            repo, settings, cid = MemoryEncounterRepository(collection, cases), \
                replace(get_settings(), collection_mode="published"), PUB
        else:
            repo, settings, cid = MemoryEncounterRepository(SYNTH.collection, SYNTH.cases), get_settings(), \
                SYNTH.collection.collection_id
        self.repo = repo
        self.svc = EncounterService(settings, repo, IntakePipeline(RuleCandidateProvider()))
        c = self.svc.create_session(CreateSessionRequest(request_id=rid(), collection_id=cid))
        self.sid, self.token, self.n = c.session_id, c.session_token, 0

    @property
    def snap(self):
        return self.svc.get_session(self.sid, self.token)

    def say(self, text: str, reply_to: str | None = None):
        self.n += 1
        s = self.svc.append_turns(self.sid, self.token, AppendTurnsRequest(
            request_id=rid(), expected_revision=self.snap.revision,
            turns=[TurnInput(turn_id=f"t{self.n}", role="patient", origin="typed", text=text,
                             reply_to_question_id=reply_to)]))
        return self.advance(s.revision)

    def advance(self, revision: int | None = None):
        return self.svc.advance(self.sid, AdvanceRequest(request_id=rid(), expected_revision=
                                                         self.snap.revision if revision is None else revision))

    def facts(self):
        return {(f.key, f.value, f.status) for f in self.snap.facts}


# ------------------------------------------------------------------ named product use

def test_product_mentions_keep_named_products_only() -> None:
    values = lambda t: [v for v, *_ in product_mentions(t)]  # noqa: E731
    assert values("I used minoxidil foam around the time it started.") == ["minoxidil foam"]
    assert values("I tried a cream, but it didn't help.") == []
    assert values("I started using a new hand soap before this began.") == []
    assert values("I used it for a few days.") == []
    assert values("I take ibuprofen and I've been using Nizoral shampoo.") == ["ibuprofen", "Nizoral shampoo"]
    assert values("I used to have this as a child.") == []


def test_minoxidil_story_keeps_the_product_without_inference() -> None:
    e = Encounter(published=True)
    r = e.say("My scalp has been itching for several days. I used minoxidil foam around the time it started.")
    facts = e.facts()
    assert ("product_use", "minoxidil_foam", "reported") in facts
    assert not any(k in ("exposure", "prior_treatment_name", "prior_treatment_response") for k, _, _ in facts)
    timeline = [i.text for i in r.snapshot.brief.timeline_items]
    assert "Patient mentions using minoxidil foam." in timeline
    assert r.snapshot.brief.prior_treatment_items == []  # purpose not stated: not a treatment
    assert r.snapshot.search_history[-1].ranked_case_ids == ["PUB-PMC7861115-1"]  # ranking unchanged by it
    # No case-report fact enters the patient's history.
    assert not any("5%" in (f.value or "") or "spray" in (f.value or "") for f in r.snapshot.facts)


def test_several_products_and_denial() -> None:
    e = Encounter()
    e.say("My hands itch. I take ibuprofen and I use Nivea lotion, but I haven't used minoxidil.")
    facts = e.facts()
    assert {("product_use", "ibuprofen", "reported"), ("product_use", "nivea_lotion", "reported"),
            ("product_use", "minoxidil", "negated")} <= facts


def test_model_product_candidates_need_use_words_and_a_name() -> None:
    turn = Turn(turn_id="t1", role="patient", origin="typed",
                text="I used minoxidil foam. Something new too. Ketoconazole shampoo is in my bathroom.",
                reply_to_question_id=None, supersedes_turn_id=None, sequence=1, created_at="2026-11-14T00:00:00Z")
    data = ExtractionInput(patient_turns=[turn], targets=[turn])
    valid, rejected = validate([
        Candidate(key="product_use", value="minoxidil foam", turn_id="t1", quote="used minoxidil foam"),
        Candidate(key="product_use", value="minoxidil foam", turn_id="t1", quote="minoxidil foam"),  # verb just before
        Candidate(key="product_use", value="Something new", turn_id="t1", quote="Something new"),  # generic
        Candidate(key="product_use", value="minoxidil 5% spray", turn_id="t1", quote="used minoxidil foam"),
        Candidate(key="product_use", value="Ketoconazole shampoo", turn_id="t1",
                  quote="Ketoconazole shampoo is in my bathroom"),  # owning is not using
    ], data)
    assert {(v.key, v.value) for v in valid} == {("product_use", "minoxidil_foam")}
    assert len(rejected) == 3


# ------------------------------------------------------------------ correction

def test_correction_supersedes_recomputes_and_invalidates_confirmation() -> None:
    e = Encounter(published=True)
    e.say("My scalp has been itching for several days.")
    confirmed = e.svc.confirm(e.sid, e.token, ConfirmRequest(request_id=rid(), expected_revision=e.snap.revision))
    assert confirmed.state == "confirmed" and confirmed.confirmed_revision == 1
    request = CorrectionRequest(request_id=rid(), expected_revision=1, replaces_turn_id="t1",
                                replacement_text="My face has been itching for several days.")
    corrected = e.svc.correct_turn(e.sid, e.token, request)
    assert corrected.revision == 2 and corrected.confirmed_revision is None and corrected.state == "intake"
    assert [t.text for t in corrected.turns][0] == "My scalp has been itching for several days."  # original kept
    new = corrected.turns[-1]
    assert new.origin == "correction" and new.supersedes_turn_id == "t1"
    assert e.svc.correct_turn(e.sid, e.token, request) == corrected  # idempotent replay
    r = e.advance()
    facts = e.facts()
    assert ("symptom_site", "itching@face", "reported") in facts and not any(v == "itching@scalp" for _, v, _ in facts)
    assert all(ref.source_id != "t1" for f in r.snapshot.facts for ref in f.evidence)  # superseded text unused
    assert r.snapshot.search_history[-1].cards == []  # the face story no longer matches the scalp case
    assert r.snapshot.brief.patient_revision == 2
    with pytest.raises(ApiError) as err:  # the superseded statement cannot be corrected again
        e.svc.correct_turn(e.sid, e.token, CorrectionRequest(request_id=rid(), expected_revision=2,
                                                             replaces_turn_id="t1", replacement_text="x"))
    assert err.value.code == "TURN_NOT_CORRECTABLE"


def test_correction_rejects_stale_revision_and_unknown_turns() -> None:
    e = Encounter()
    e.say("My hands have been itchy for weeks.")
    for req, code in ((CorrectionRequest(request_id=rid(), expected_revision=0, replaces_turn_id="t1",
                                         replacement_text="x"), "REVISION_CONFLICT"),
                      (CorrectionRequest(request_id=rid(), expected_revision=1, replaces_turn_id="nope",
                                         replacement_text="x"), "TURN_NOT_FOUND")):
        with pytest.raises(ApiError) as err:
            e.svc.correct_turn(e.sid, e.token, req)
        assert err.value.code == code
    assert e.snap.revision == 1


def test_correcting_an_answer_keeps_the_question_budget() -> None:
    e = Encounter()
    first = e.say("My hands have been itchy for weeks. I tried a cream, but it didn't help.")
    q = first.question
    e.say("I don't remember the name. I used it for a few days.", reply_to=q.question_id)
    asked_before = [x.question_id for x in e.snap.questions]
    e.svc.correct_turn(e.sid, e.token, CorrectionRequest(request_id=rid(), expected_revision=e.snap.revision,
                                                         replaces_turn_id="t2",
                                                         replacement_text="It was called Eucerin, used a week."))
    r = e.advance()
    assert [x.question_id for x in r.snapshot.questions] == asked_before  # no new or repeated question
    assert ("prior_treatment_name", "eucerin", "reported") in e.facts()
    assert r.snapshot.questions[0].answer_turn_ids == [r.snapshot.turns[-1].turn_id]


# ------------------------------------------------------------------ skip

def test_skip_records_skipped_not_a_negative_and_is_not_reasked() -> None:
    e = Encounter(published=True)
    first = e.say("My face is itchy.")
    q = first.question
    assert q is not None and q.template_id == "duration_v1"
    request = SkipQuestionRequest(request_id=rid(), expected_revision=1, question_id=q.question_id)
    skipped = e.svc.skip_question(e.sid, e.token, request)
    assert skipped.revision == 2 and skipped.questions[0].status == "skipped" and skipped.confirmed_revision is None
    assert e.svc.skip_question(e.sid, e.token, request) == skipped  # idempotent replay
    r = e.advance()
    assert r.action == "ready_to_confirm" and r.question is None
    assert [x.status for x in r.snapshot.questions] == ["skipped"]
    assert not any(f.key == "duration" for f in r.snapshot.facts)  # skipped is not "no duration"
    assert any(i.text.startswith("Clarification skipped by the patient") and i.status == "missing"
               for i in r.snapshot.brief.unresolved_items)
    with pytest.raises(ApiError) as err:
        e.svc.skip_question(e.sid, e.token, SkipQuestionRequest(request_id=rid(), expected_revision=2,
                                                                question_id=q.question_id))
    assert err.value.code == "QUESTION_NOT_PENDING"
    e.svc.confirm(e.sid, e.token, ConfirmRequest(request_id=rid(), expected_revision=2))
    assert e.snap.confirmed_revision == 2
