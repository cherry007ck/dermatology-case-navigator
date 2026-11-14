"""Two-question policy (docs/04-data-and-evidence.md "Question policy — maximum two questions total").

Templates are a prototype checklist, NOT clinician-reviewed. Patient-facing text never names a
diagnosis, a treatment or a case. At most one intake-gap question and one case-difference
question per encounter; each is offered once and never re-asked.

Question IDs are opaque to clients. They encode the patient-turn sequence after which the question
was asked (``Q<n>.t<seq>``) so a later voice turn with no ``reply_to_question_id`` can be linked
to the pending question by sequence (contract voice step 7), never to an earlier turn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Question, Turn

QUESTION_KEYS: dict[str, tuple[str, ...]] = {
    "cream_details_v1": ("prior_treatment_name", "prior_treatment_duration"),
    "duration_v1": ("duration",),
    "site_v1": ("site",),
    "symptom_v1": ("symptom",),
    "exposure_context_v1": ("exposure",),
}
CHECKLIST_NOTE = "Prototype intake checklist; not clinician-reviewed."
EXPOSURE_TEXT = "Before this started, did you notice any change in products, gloves, or activities involving your hands?"
CHECKLIST = (
    ("site", "site_v1", "Where on your body is it?", "No body site was mentioned."),
    ("symptom", "symptom_v1", "How would you describe what you feel there?", "No symptom was described."),
    ("duration", "duration_v1", "How long have you had this?", "No duration was mentioned."),
)
_ID = re.compile(r"^Q(\d+)\.t(\d+)$")


def question_id(number: int, after_sequence: int) -> str:
    return f"Q{number}.t{after_sequence}"


def asked_after(question: Question) -> int:
    """Patient-turn sequence the question was asked after (0 for IDs this module did not issue)."""
    m = _ID.match(question.question_id)
    return int(m.group(2)) if m else 0


@dataclass(frozen=True)
class Link:
    question: Question
    answer_turn: Turn | None


def link_answers(questions: list[Question], patient_turns: list[Turn], is_ack) -> dict[str, Link]:
    """Map each asked/answered question to the patient turn that answers it.

    Explicit ``reply_to_question_id`` wins. Otherwise the first non-acknowledgement patient turn
    after the question was asked answers it. Turns before the question never do.
    """
    links: dict[str, Link] = {}
    used: set[str] = set()
    for q in questions:
        explicit = [t for t in patient_turns if t.reply_to_question_id == q.question_id and not is_ack(t.text)]
        later = [t for t in patient_turns if t.sequence > asked_after(q) and t.reply_to_question_id in (None, q.question_id)
                 and not is_ack(t.text) and t.turn_id not in used]
        answer = (explicit or later or [None])[0]
        if answer is not None:
            used.add(answer.turn_id)
        links[q.question_id] = Link(q, answer)
    return links
