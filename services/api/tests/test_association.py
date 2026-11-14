"""structured-v2 symptom–site associations: no cross-pairing, evidence for the association itself,
conservative handling of ambiguity/negation, and honest treatment of stored structured-v1 searches."""
from __future__ import annotations

import json
import uuid
from dataclasses import replace

from app.config import REPO_ROOT, get_settings
from app.extraction import association
from app.extraction.meta import RESPONSE_SCHEMA
from app.extraction.rules import RuleCandidateProvider
from app.fixtures import get_fixture_bundle
from app.models import (AdvanceRequest, AppendTurnsRequest, CreateSessionRequest, SessionSnapshot, TurnInput)
from app.pipeline import IntakePipeline
from app.published import build_collection, read_records
from app.repositories.memory import MemoryEncounterRepository
from app.retrieval import structured_v2 as ranking
from app.service import EncounterService

PUB = "published-derm-v1"
SYNTH = get_fixture_bundle()
CANDIDATES = read_records(REPO_ROOT / "data" / "published" / "candidates")


def _reviewed(raw: dict) -> dict:
    return {**raw, "source_review": {"status": "reviewed", "reviewer": "test reviewer",
                                     "reviewed_at": "2026-11-13T12:00:00Z"}}


class _Published(MemoryEncounterRepository):
    def __init__(self) -> None:
        collection, cases = build_collection([_reviewed(r) for r in CANDIDATES], PUB)
        super().__init__(collection, cases)


class Encounter:
    def __init__(self, published: bool = False) -> None:
        if published:
            repo = _Published()
            settings = replace(get_settings(), collection_mode="published")
            collection_id = PUB
        else:
            repo = MemoryEncounterRepository(SYNTH.collection, SYNTH.cases)
            settings = get_settings()
            collection_id = SYNTH.collection.collection_id
        self.svc = EncounterService(settings, repo, IntakePipeline(RuleCandidateProvider()))
        c = self.svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()), collection_id=collection_id))
        self.sid, self.token, self.revision, self.n = c.session_id, c.session_token, 0, 0

    def say(self, text: str):
        self.n += 1
        snap = self.svc.append_turns(self.sid, self.token, AppendTurnsRequest(
            request_id=str(uuid.uuid4()), expected_revision=self.revision,
            turns=[TurnInput(turn_id=f"t{self.n}", role="patient", origin="typed", text=text,
                             reply_to_question_id=None)]))
        self.revision = snap.revision
        return self.svc.advance(self.sid, AdvanceRequest(request_id=str(uuid.uuid4()), expected_revision=self.revision))

    def assoc(self) -> set[tuple[str, str]]:
        return {(f.value, f.status) for f in self.svc.get_session(self.sid, self.token).facts
                if f.key == association.KEY}


def _pairs(text: str) -> set[tuple[str, bool]]:
    return {(lk.value, lk.negated) for lk in association.links(text) if not lk.uncertain}


# ------------------------------------------------------------------ linking rule

def test_only_symptoms_stated_at_a_site_are_linked() -> None:
    assert _pairs("My scalp has been really itchy.") == {("itching@scalp", False)}
    assert _pairs("itching on my hands for weeks") == {("itching@hands", False)}
    assert _pairs("My scalp itches and my face is red.") == {("itching@scalp", False), ("redness@face", False)}
    assert _pairs("I have itchy hands and feet.") == {("itching@hands", False)}  # list item not paired
    assert _pairs("My hands and face are itchy.") == {("itching@face", False)}  # conservative, no cross-pair
    assert _pairs("It itches. It's on my scalp.") == set()  # separate sentences
    assert _pairs("My scalp, it's just itchy.") == set()  # comma-separated topic is not a stated link
    assert _pairs("Itching, redness, scalp, face.") == set()  # a bare list proves nothing


def test_negated_and_uncertain_links() -> None:
    assert _pairs("My hands aren't itchy.") == {("itching@hands", True)}
    assert _pairs("There is no rash on my arms.") == {("rash@arms", True)}
    assert _pairs("I'm not sure if my scalp itches.") == set()
    assert _pairs("No redness, but my hands itch.") == {("itching@hands", False)}


def test_meta_schema_allows_the_key_and_the_validator_decides() -> None:
    enum = RESPONSE_SCHEMA["properties"]["facts"]["items"]["properties"]["key"]["enum"]
    assert association.KEY in enum
    assert association.supported("My scalp itches and my face is swollen", 0, 38, "itching@face", False) == \
        "association_not_stated_together"
    assert association.supported("My scalp itches", 0, 15, "itching@scalp", True) == "negation_mismatch"
    assert association.supported("My scalp itches", 0, 15, "itching-scalp", False) == "association_value_format"


# ------------------------------------------------------------------ published retrieval

def test_scalp_itching_matches_the_supported_scalp_itching_case() -> None:
    e = Encounter(published=True)
    r = e.say("My scalp has been really itchy.")
    search = r.snapshot.search_history[-1]
    assert search.algorithm_version == "structured-v2"
    assert search.ranked_case_ids == ["PUB-PMC7861115-1"]
    shared = search.cards[0].shared_features[0]
    assert shared.text == "Shared reported symptom at the same site: itching on the scalp."
    patient_ref, case_ref = shared.evidence
    assert patient_ref.source_type == "patient_turn" and patient_ref.quote == "scalp has been really itchy"
    assert case_ref.source_type == "case_passage" and case_ref.quote == "itchiness over the scalp"


def test_itchy_face_does_not_qualify_through_scalp_itching_and_facial_swelling() -> None:
    e = Encounter(published=True)
    r = e.say("My face is itchy.")
    search = r.snapshot.search_history[-1]
    assert search.cards == [] and search.no_match_reason == "no_comparable_cases"
    reasons = {x.case_id: x.reason for x in search.excluded_cases}
    assert reasons["PUB-PMC7861115-1"] == "no_shared_symptom"


def test_multiple_symptoms_and_sites_create_no_cross_pairs() -> None:
    e = Encounter(published=True)
    r = e.say("My scalp is red and my face itches.")
    assert e.assoc() == {("redness@scalp", "reported"), ("itching@face", "reported")}
    assert r.snapshot.search_history[-1].cards == []  # neither stated pair exists in the case


def test_negated_association_never_matches_and_is_cited() -> None:
    e = Encounter(published=True)
    r = e.say("My scalp isn't itchy.")
    assert e.assoc() == {("itching@scalp", "negated")}
    search = r.snapshot.search_history[-1]
    assert search.cards == [] and search.no_match_reason == "insufficient_information"
    ex = next(x for x in search.excluded_cases if x.case_id == "PUB-PMC7861115-1")
    assert ex.reason == "no_shared_symptom" and [ref.quote for ref in ex.evidence] == [
        "scalp isn't itchy", "itchiness over the scalp"]
    assert any(i.text == "Patient denies itching on the scalp." for i in r.snapshot.brief.summary_items)


def test_contradictory_association_is_conflicting_not_a_match() -> None:
    e = Encounter(published=True)
    e.say("My scalp itches.")
    r = e.say("Actually my scalp doesn't itch.")
    assert e.assoc() == {(None, "conflicting")}
    assert r.snapshot.search_history[-1].cards == []


# ------------------------------------------------------------------ synthetic and answers

def test_synthetic_legacy_cases_link_only_what_their_passages_state() -> None:
    e = Encounter()
    r = e.say("My hands have been itchy for weeks.")
    search = r.snapshot.search_history[-1]
    assert search.ranked_case_ids == ["SYN-A", "SYN-B"]
    case_quotes = {ref.quote for card in search.cards for s in card.shared_features[:1] for ref in s.evidence
                   if ref.source_type == "case_passage"}
    assert case_quotes == {"itching on the hands"}
    assert json.loads((REPO_ROOT / "data/synthetic/collection.json").read_text(encoding="utf-8"))["version"] == \
        SYNTH.collection.version  # fixture digest unchanged: synthetic records are not rewritten


def test_answer_to_the_site_question_links_the_single_reported_symptom() -> None:
    e = Encounter()
    first = e.say("My skin itches a lot.")
    assert first.question.template_id == "site_v1"
    r = e.say("On my hands.")
    facts = [f for f in r.snapshot.facts if f.key == association.KEY]
    assert [(f.value, f.status) for f in facts] == [("itching@hands", "reported")]
    assert [ref.quote for ref in facts[0].evidence] == ["itches", "hands"]
    assert r.snapshot.search_history[-1].ranked_case_ids == ["SYN-A", "SYN-B"]


def test_answer_does_not_guess_between_several_symptoms() -> None:
    e = Encounter()
    first = e.say("It itches and it burns.")
    assert first.question.template_id == "site_v1"
    e.say("On my hands.")
    assert e.assoc() == set()


# ------------------------------------------------------------------ stored v1 searches

def test_stored_structured_v1_search_stays_readable_and_is_not_reinterpreted() -> None:
    raw = json.loads((REPO_ROOT / "contracts/examples/after-initial.json").read_text(encoding="utf-8"))
    stored = SessionSnapshot.model_validate(raw["snapshot"]).search_history[-1]
    assert stored.algorithm_version == "structured-v1" and stored.ranked_case_ids  # readable as stored
    facts = SessionSnapshot.model_validate(raw["snapshot"]).facts
    ranked, excluded, _ = ranking.rank(facts, SYNTH.cases, SYNTH.collection)
    changes = ranking.diff(stored, ranked, excluded)
    assert changes and all(c.reason.startswith("Comparison rules changed to structured-v2") for c in changes)
    assert ranking.search_id("s", stored.patient_revision, SYNTH.collection, facts) != stored.search_id
