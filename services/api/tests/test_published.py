"""Published collection: candidate validation, review gate, isolation from synthetic, card provenance.

Uses the real pending candidates in data/published/candidates/. "Reviewed" copies are made in
memory for these tests only; nothing on disk is marked reviewed.
"""
from __future__ import annotations

import copy
import hashlib
import uuid
from dataclasses import replace

import pytest

from app.config import get_settings
from app.errors import ApiError
from app.extraction.rules import RuleCandidateProvider
from app.fixtures import get_fixture_bundle
from app.models import AdvanceRequest, AppendTurnsRequest, CreateSessionRequest, TurnInput
from app.pipeline import IntakePipeline
from app.published import PublishedRecordError, build_collection, read_records
from app.repositories.memory import MemoryEncounterRepository
from app.retrieval import structured_v2 as ranking
from app.service import EncounterService

PUB = "published-derm-v1"
CANDIDATES = read_records(get_settings().fixture_root / "data" / "published" / "candidates")
SYNTH = get_fixture_bundle()


def reviewed(raw: dict) -> dict:
    out = copy.deepcopy(raw)
    out["source_review"] = {"status": "reviewed", "reviewer": "test reviewer", "reviewed_at": "2026-11-13T12:00:00Z"}
    return out


class TwoCollections(MemoryEncounterRepository):
    """Memory repository holding the synthetic and a published collection side by side."""

    def __init__(self, published, published_cases) -> None:
        super().__init__(SYNTH.collection, [*SYNTH.cases, *published_cases])
        self._published = published

    def list_collections(self):
        return [self._collection, self._published]


def published_service(mode: str = "published") -> EncounterService:
    collection, cases = build_collection([reviewed(r) for r in CANDIDATES], PUB)
    repo = TwoCollections(collection, cases)
    return EncounterService(replace(get_settings(), collection_mode=mode), repo,
                            IntakePipeline(RuleCandidateProvider()))


def test_candidates_are_valid_pending_and_never_clinically_reviewed() -> None:
    assert len(CANDIDATES) >= 2
    collection, cases = build_collection(CANDIDATES, PUB, require_reviewed=False)
    assert collection.mode == "published" and collection.source_review_count == 0
    assert collection.clinical_reviewed is False
    for case in cases:
        assert case.source_review.status == "pending" and case.source_review.reviewer is None
        assert case.clinical_reviewed is False
        assert case.article_url == f"https://pmc.ncbi.nlm.nih.gov/articles/{case.article_identifiers['pmcid']}/"
        assert case.license.startswith("CC BY")


def test_pending_records_cannot_be_imported() -> None:
    with pytest.raises(PublishedRecordError, match="only reviewed records"):
        build_collection(CANDIDATES, PUB)
    half = [reviewed(CANDIDATES[0]), *CANDIDATES[1:]]
    with pytest.raises(PublishedRecordError, match="only reviewed records"):
        build_collection(half, PUB)


def test_reviewed_without_reviewer_is_refused() -> None:
    bad = reviewed(CANDIDATES[0])
    bad["source_review"]["reviewer"] = " "
    with pytest.raises(PublishedRecordError):
        build_collection([bad], PUB)


def test_cross_case_passage_reference_is_rejected() -> None:
    a, b = reviewed(CANDIDATES[0]), reviewed(CANDIDATES[1])
    foreign = b["passages"][0]
    a["features"][0]["evidence"] = [{"source_type": "case_passage", "source_id": foreign["passage_id"],
                                     "quote": foreign["text"][:20]}]
    with pytest.raises(PublishedRecordError, match="not a quote from this case"):
        build_collection([a, b], PUB)
    a2 = reviewed(CANDIDATES[0])
    a2["passages"].append({**foreign})  # a passage owned by another case smuggled into this record
    with pytest.raises(PublishedRecordError, match="belongs to another case"):
        build_collection([a2], PUB)


def test_edited_passage_text_or_quote_is_rejected() -> None:
    edited = reviewed(CANDIDATES[0])
    edited["passages"][0]["text"] += " Extra words."
    with pytest.raises(PublishedRecordError, match="hash mismatch"):
        build_collection([edited], PUB)
    invented = reviewed(CANDIDATES[0])
    invented["outcomes"][0]["evidence"][0]["quote"] = "complete resolution"
    with pytest.raises(PublishedRecordError, match="not a quote"):
        build_collection([invented], PUB)


def test_synthetic_records_and_ids_cannot_enter_the_published_collection() -> None:
    synthetic = SYNTH.cases[0].model_dump(mode="json")
    with pytest.raises(PublishedRecordError):
        build_collection([reviewed(CANDIDATES[0]), synthetic], PUB)
    with pytest.raises(PublishedRecordError, match="start with"):
        build_collection([reviewed(CANDIDATES[0])], "synthetic-demo-v1")


def test_collection_version_changes_with_content() -> None:
    first, _ = build_collection([reviewed(r) for r in CANDIDATES], PUB)
    again, _ = build_collection([reviewed(r) for r in reversed(CANDIDATES)], PUB)
    changed = [reviewed(r) for r in CANDIDATES]
    changed[0]["title"] += " (edited)"
    other, _ = build_collection(changed, PUB)
    assert first.version == again.version != other.version


def test_ranking_excludes_pending_and_wrong_kind_cases() -> None:
    collection, cases = build_collection([reviewed(r) for r in CANDIDATES], PUB)
    _, pending = build_collection(CANDIDATES, PUB, require_reviewed=False)
    _, excluded, no_match = ranking.rank([], [*pending, *SYNTH.cases], collection)
    reasons = {e.case_id: e.reason for e in excluded}
    assert all(reasons[c.case_id] == "unreviewed_source" for c in pending)
    assert all(reasons[c.case_id] == "source_mode_mismatch" for c in SYNTH.cases)
    assert no_match == "insufficient_information"


def _encounter(svc: EncounterService, collection_id: str, text: str):
    created = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()), collection_id=collection_id))
    snap = svc.append_turns(created.session_id, created.session_token, AppendTurnsRequest(
        request_id=str(uuid.uuid4()), expected_revision=0,
        turns=[TurnInput(turn_id="t1", role="patient", origin="typed", text=text, reply_to_question_id=None)]))
    return svc.advance(created.session_id, AdvanceRequest(request_id=str(uuid.uuid4()), expected_revision=snap.revision))


def test_modes_list_only_their_own_collection() -> None:
    assert [c.collection_id for c in published_service("published").list_collections().collections] == [PUB]
    assert [c.collection_id for c in published_service("synthetic").list_collections().collections] == \
        ["synthetic-demo-v1"]
    with pytest.raises(ApiError):
        published_service("published").create_session(
            CreateSessionRequest(request_id=str(uuid.uuid4()), collection_id="synthetic-demo-v1"))
    with pytest.raises(ApiError):
        published_service("synthetic").create_session(
            CreateSessionRequest(request_id=str(uuid.uuid4()), collection_id=PUB))


def test_published_encounter_returns_real_cards_with_own_passages() -> None:
    result = _encounter(published_service(), PUB, "My fingers have been itchy for a few days.")
    search = result.snapshot.search_history[-1]
    assert search.ranked_case_ids == ["PUB-PMC7647841-1"]
    card = search.cards[0]
    assert card.source_kind == "published" and card.article_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC7647841/"
    own = {p.passage_id: p for p in card.passages}
    assert own and all(p.case_id == card.case_id for p in own.values())
    assert all(hashlib.sha256(p.text.encode()).hexdigest() == p.sha256 for p in own.values())
    for statement in [*card.shared_features, *card.important_differences, *card.actions, *card.outcomes]:
        for ref in statement.evidence:
            if ref.source_type == "case_passage":
                assert ref.source_id in own and ref.quote in own[ref.source_id].text
    assert not any(c.startswith("SYN-") for c in search.ranked_case_ids)
    a = card.attribution
    assert a is not None and a.pmcid == "PMC7647841" and a.pmid == "33173645" and a.doi == "10.7759/cureus.10839"
    assert a.authors == ["Calle Sarmiento PM", "Chango Azanza JJ"] and (a.journal, a.year) == ("Cureus", "2020")
    assert (a.license_name, a.license_url) == ("CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/")
    assert a.source_review_status == "reviewed" and a.clinical_reviewed is False


def test_published_snapshots_never_carry_the_fictional_label() -> None:
    published = _encounter(published_service(), PUB, "My fingers have been itchy for a few days.").snapshot
    synthetic = _encounter(published_service("synthetic"), "synthetic-demo-v1", "My hands have been itchy.").snapshot
    assert not any("Fictional" in w for w in published.warnings)
    assert any("not clinically reviewed" in w for w in published.warnings)
    assert any(w.startswith("Fictional demonstration cases") for w in synthetic.warnings)


def test_synthetic_cards_have_null_attribution_in_the_serialized_response() -> None:
    result = _encounter(published_service("synthetic"), "synthetic-demo-v1", "My hands have been itchy for weeks.")
    cards = result.snapshot.model_dump(mode="json")["search_history"][-1]["cards"]
    assert cards and all(c["source_kind"] == "synthetic" and "attribution" in c and c["attribution"] is None
                         for c in cards)


def test_pending_or_uncited_records_get_no_attribution_and_cannot_import() -> None:
    _, pending = build_collection(CANDIDATES, PUB, require_reviewed=False)
    assert all(ranking.attribution(c) is None for c in pending)
    uncited = reviewed(CANDIDATES[0])
    del uncited["citation"]
    with pytest.raises(PublishedRecordError, match="citation"):
        build_collection([uncited], PUB)
    mismatch = reviewed(CANDIDATES[0])
    mismatch["citation"]["license_name"] = "CC BY 4.0"
    with pytest.raises(PublishedRecordError, match="licence fields"):
        build_collection([mismatch], PUB)


def test_minoxidil_case_has_no_generic_duration_and_keeps_raw_exposure() -> None:
    case = next(c for c in CANDIDATES if c["case_id"] == "PUB-PMC7861115-1")
    keys = {(f["key"], f["value"]) for f in case["features"]}
    assert not any(k == "duration" for k, _ in keys)
    assert ("exposure", "topical_minoxidil_foam") in keys and ("exposure", "new_product") not in keys


def test_synthetic_records_serialize_without_a_citation_field() -> None:
    for case in SYNTH.cases:
        assert "citation" not in case.model_dump(mode="json")


def test_published_encounter_has_an_honest_no_match() -> None:
    result = _encounter(published_service(), PUB, "My feet have been itchy for weeks.")
    search = result.snapshot.search_history[-1]
    assert search.cards == [] and search.no_match_reason == "no_comparable_cases"
    assert result.snapshot.brief is not None
