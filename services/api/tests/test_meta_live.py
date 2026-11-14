"""Live Meta Model API extraction on unseen, hesitant fictional wording.

    $env:DCN_LIVE_META="1"; python -m pytest tests/test_meta_live.py -s

Skipped unless DCN_LIVE_META=1 and MODEL_API_KEY / MODEL_BASE_URL / MODEL_NAME are set. Asserts
facts the wording clearly supports plus what the server validator guarantees (every quote is an
exact substring of its patient turn). Prints only latency per call. CI never runs this.
"""
from __future__ import annotations

import os
import uuid

import pytest

from app.config import get_settings
from app.extraction.meta import MetaCandidateProvider
from app.fixtures import get_fixture_bundle
from app.models import AdvanceRequest, AppendTurnsRequest, CreateSessionRequest, TurnInput
from app.pipeline import IntakePipeline
from app.repositories.memory import MemoryEncounterRepository
from app.service import EncounterService

settings = get_settings()
pytestmark = pytest.mark.skipif(
    os.getenv("DCN_LIVE_META") != "1"
    or not (settings.model_api_key and settings.model_base_url and settings.model_name),
    reason="live Meta check: set DCN_LIVE_META=1 and MODEL_API_KEY/MODEL_BASE_URL/MODEL_NAME in services/api/.env",
)


def run(lines: list[str]):
    bundle = get_fixture_bundle()
    provider = MetaCandidateProvider(settings.model_api_key, settings.model_base_url, settings.model_name)
    svc = EncounterService(settings, MemoryEncounterRepository(bundle.collection, bundle.cases), IntakePipeline(provider))
    c = svc.create_session(CreateSessionRequest(request_id=str(uuid.uuid4()), collection_id="synthetic-demo-v1"))
    revision, results = 0, []
    for i, text in enumerate(lines):
        revision = svc.append_turns(c.session_id, c.session_token, AppendTurnsRequest(
            request_id=str(uuid.uuid4()), expected_revision=revision,
            turns=[TurnInput(turn_id=f"m{i}", role="patient", origin="voice_transcript", text=text,
                             reply_to_question_id=None)])).revision
        results.append(svc.advance(c.session_id, AdvanceRequest(request_id=str(uuid.uuid4()), expected_revision=revision)))
        if provider.last_latency_seconds is not None:
            print(f"meta latency turn {i + 1}: {provider.last_latency_seconds:.2f}s")
    return results


def facts(result):
    return {(f.key, f.value, f.status) for f in result.snapshot.facts}


def quotes_are_exact(result) -> None:
    turns = {t.turn_id: t for t in result.snapshot.turns}
    for f in result.snapshot.facts:
        for ref in f.evidence:
            assert turns[ref.source_id].role == "patient" and ref.quote in turns[ref.source_id].text


def test_hesitant_paraphrase_main_story() -> None:
    r = run([
        "Uh, hi, so, um, the backs of my hands keep itching, it's been, like, three weeks? I rubbed some cream on, "
        "didn't make any difference honestly.",
        "No clue what it was called, sorry. I only used it a couple of days.",
        "Oh, yeah, actually I switched to a new hand soap right before it started.",
    ])
    assert [x.action for x in r] == ["ask", "ask", "ready_to_confirm"]
    final = facts(r[-1])
    assert {("site", "hands", "reported"), ("symptom", "itching", "reported"), ("duration", "weeks", "reported"),
            ("exposure", "new_product", "reported")} <= final
    assert ("prior_treatment_name", None, "unknown") in final
    assert not any(k == "prior_treatment_name" and v for k, v, _ in final)  # never a drug from "cream"
    assert r[-1].snapshot.search_history[-1].ranked_case_ids == ["SYN-A"]
    quotes_are_exact(r[-1])


def test_denial_and_no_new_products_paraphrase() -> None:
    r = run([
        "Okay so, my hands, they're not itchy exactly, more like they burn? Few weeks now.",
        "Hmm. No, nothing new, same soap I've always used.",
    ])
    final = facts(r[-1])
    assert ("symptom", "burning", "reported") in final
    assert ("symptom", "itching", "negated") in final
    quotes_are_exact(r[-1])
    assert r[-1].snapshot.search_history[-1].ranked_case_ids == []  # burning shares no symptom with the hand cases


def test_no_match_paraphrase() -> None:
    r = run(["Hmm, my scalp just feels kind of uncomfortable? I genuinely don't know when it started."])
    last = r[-1].snapshot.search_history[-1]
    assert last.cards == [] and last.no_match_reason == "no_comparable_cases"
    assert ("site", "scalp", "reported") in facts(r[-1])
    quotes_are_exact(r[-1])


def test_separate_symptoms_and_sites_are_not_cross_paired() -> None:
    """structured-v2: ordinary wording with two symptoms at two sites. Whatever the model proposes,
    only associations stated together survive validation; no cross-pair is ever a fact."""
    r = run(["So my scalp has been itching for weeks, and, um, my face got a bit red too."])[-1]
    quotes_are_exact(r)
    assoc = {(v, s) for k, v, s in facts(r) if k == "symptom_site"}
    assert ("itching@face", "reported") not in assoc and ("redness@scalp", "reported") not in assoc
    assert ("itching@scalp", "reported") in assoc
    assert r.snapshot.search_history[-1].algorithm_version == "structured-v2"
