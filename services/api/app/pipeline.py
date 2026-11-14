"""Intake pipeline behind ``IntakeService.advance``: extract → validate → rank → question → brief.

1. Active patient turns only (agent turns and superseded turns never reach the provider or the
   validator as evidence). Pure acknowledgements are skipped.
2. The configured candidate provider (Meta Model API, or the labelled deterministic keyword rules) proposes
   candidate facts; ``app.evidence.validate`` keeps only those supported by the patient's words.
3. ``structured-v2`` ranks the stored cases from those facts; a new immutable search version is
   created only when its inputs (or the algorithm version) changed. Stored ``structured-v1``
   searches are never recomputed or relabelled.
4. The two-question policy decides whether to ask; then a template brief is rendered.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.evidence.brief import build_brief, treatment_mention
from app.evidence.validate import Rejected, answer_associations, assemble_facts, validate
from app.extraction.candidates import CandidateProvider, ExtractionInput
from app.extraction.vocabulary import ACKNOWLEDGEMENT, EXPOSURE_GATE_VALUES, STOP_CUE
from app.models import (
    Brief,
    CaseRecord,
    Collection,
    ComparisonBasis,
    EvidenceRef,
    PatientFact,
    Question,
    SearchVersion,
    SessionState,
    Turn,
)
from app.questions import CHECKLIST, CHECKLIST_NOTE, EXPOSURE_TEXT, QUESTION_KEYS, link_answers, question_id
from app.retrieval import structured_v2 as ranking

MAX_QUESTIONS = 2


def is_ack(text: str) -> bool:
    return bool(ACKNOWLEDGEMENT.match(text))


def active_patient_turns(turns: list[Turn]) -> list[Turn]:
    superseded = {t.supersedes_turn_id for t in turns if t.supersedes_turn_id}
    return sorted((t for t in turns if t.role == "patient" and t.turn_id not in superseded), key=lambda t: t.sequence)


@dataclass(frozen=True)
class Outcome:
    action: str  # ask | ready_to_confirm | waiting_for_transcript
    facts: list[PatientFact]
    questions: list[Question]
    new_search: SearchVersion | None
    brief: Brief | None
    state: SessionState
    question: Question | None
    rejected: list[Rejected]


class IntakePipeline:
    def __init__(self, provider: CandidateProvider) -> None:
        self.provider = provider

    @property
    def mode(self) -> str:
        return self.provider.mode

    @property
    def configured(self) -> bool:
        return bool(getattr(self.provider, "configured", True))

    def process(self, *, session_id: str, revision: int, turns: list[Turn], questions: list[Question],
                search_history: list[SearchVersion], collection: Collection, cases: list[CaseRecord],
                now: datetime | None = None) -> Outcome:
        patient = active_patient_turns(turns)
        substantive = [t for t in patient if not is_ack(t.text)]
        if not substantive:
            return Outcome("waiting_for_transcript", [], questions, None, None, "intake", None, [])

        links = link_answers(questions, patient, is_ack)
        answered_by = {link.answer_turn.turn_id: link.question for link in links.values() if link.answer_turn}
        data = ExtractionInput(patient_turns=patient, targets=substantive, questions=answered_by)
        candidates = self.provider.extract(data)  # ExtractionUnavailable propagates to the service
        valid, rejected = validate(candidates, data)
        valid += answer_associations(valid, data)
        facts = assemble_facts(valid)

        updated: list[Question] = []
        for q in questions:
            answer = links[q.question_id].answer_turn
            if q.status == "skipped" or answer is None:
                updated.append(q if q.status == "skipped" else q.model_copy(update={"status": "asked", "answer_turn_ids": []}))
                continue
            keys = QUESTION_KEYS.get(q.template_id, ())
            mine = [v for v in valid if v.turn.turn_id == answer.turn_id and v.key in keys]
            status = "unknown" if mine and all(v.status == "unknown" for v in mine) else "answered"
            updated.append(q.model_copy(update={"status": status, "answer_turn_ids": [answer.turn_id]}))

        ranked, excluded, no_match = ranking.rank(facts, cases, collection)
        previous = search_history[-1] if search_history else None
        sid = ranking.search_id(session_id, revision, collection, facts)
        new_search = None
        if previous is None or previous.search_id != sid:
            new_search = SearchVersion(
                search_id=sid, patient_revision=revision, algorithm_version=ranking.ALGORITHM_VERSION,
                collection_version=collection.version, input_fact_ids=[f.fact_id for f in facts],
                ranked_case_ids=[r.case.record.case_id for r in ranked], cards=[ranking.card(r) for r in ranked],
                excluded_cases=excluded, score_components=[r.score for r in ranked],
                changes=ranking.diff(previous, ranked, excluded), no_match_reason=no_match,
                created_at=(now or datetime.now(UTC)).replace(microsecond=0),
            )

        question = self._next_question(updated, facts, patient, ranked, collection)
        if question is not None and question not in updated:
            updated.append(question)
        brief = build_brief(revision, facts, patient, updated, [r.case.record.case_id for r in ranked])
        if question is not None:
            return Outcome("ask", facts, updated, new_search, brief, "awaiting_answer", question, rejected)
        return Outcome("ready_to_confirm", facts, updated, new_search, brief, "ready_to_confirm", None, rejected)

    def _next_question(self, questions: list[Question], facts: list[PatientFact], patient: list[Turn],
                       ranked: list, collection: Collection) -> Question | None:
        pending = [q for q in questions if q.status == "asked"]
        if pending:
            return pending[0]  # never stack questions; never re-issue a new one for the same answer
        if len(questions) >= MAX_QUESTIONS or any(STOP_CUE.search(t.text) for t in patient):
            return None
        kinds = {q.kind for q in questions}
        after = patient[-1].sequence
        number = len(questions) + 1
        keys = {f.key for f in facts}
        if "onset" in keys:
            keys.add("duration")  # "when it began" answers "how long" (known or explicitly unknown): never re-ask
        if "intake_gap" not in kinds:
            mention = treatment_mention(patient)
            if mention and not keys & {"prior_treatment_name", "prior_treatment_duration"}:
                form, ref = mention
                return Question(
                    question_id=question_id(number, after), kind="intake_gap", template_id="cream_details_v1",
                    text=f"Do you know the {form}'s name and how long you used it?", status="asked", evidence=[ref],
                    reason=f"A {form} was reported without its name or duration of use. {CHECKLIST_NOTE}",
                    comparison_basis=None, answer_turn_ids=[])
            if not mention:
                for key, template, text, why in CHECKLIST:
                    if key not in keys:
                        return Question(question_id=question_id(number, after), kind="intake_gap",
                                        template_id=template, text=text, status="asked", evidence=[],
                                        reason=f"{why} {CHECKLIST_NOTE}", comparison_basis=None, answer_turn_ids=[])
        if "case_difference" not in kinds:
            return self._exposure_question(number, after, facts, ranked, collection)
        return None

    @staticmethod
    def _exposure_question(number: int, after: int, facts: list[PatientFact], ranked: list,
                           collection: Collection) -> Question | None:
        # Synthetic mechanics only: in published mode this question would need clinician approval.
        if collection.mode != "synthetic" or any(f.key == "exposure" for f in facts):
            return None
        if not any(f.key == "site" and f.value == "hands" and f.status == "reported" for f in facts):
            return None
        holders: dict[str, tuple[str, EvidenceRef]] = {}
        for r in ranked:
            for value, refs in r.case.affirmed.get("exposure", {}).items():
                if value in EXPOSURE_GATE_VALUES and value not in holders and refs:
                    holders[value] = (r.case.record.case_id, refs[0])
        if len(holders) < 2:
            return None
        pair = [holders[v] for v in sorted(holders)]
        return Question(
            question_id=question_id(number, after), kind="case_difference", template_id="exposure_context_v1",
            text=EXPOSURE_TEXT, status="asked", evidence=[],
            reason="The eligible fictional cases explicitly differ on new-product history; this is a mechanics "
                   "demonstration, not a validated clinical question.",
            comparison_basis=ComparisonBasis(case_ids=[cid for cid, _ in pair], contrasting_feature="exposure",
                                             evidence=[ref for _, ref in pair]),
            answer_turn_ids=[])
