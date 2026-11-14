"""Deterministic keyword candidate provider (``extractor = "fixture"``, shown as "Demo extraction").

Not a language model. It proposes candidates from the server alias vocabulary over any wording,
so tests and CI exercise the same validation, ranking, question and brief pipeline as Meta
mode without network access. Every candidate still goes through ``app.evidence.validate``.
"""
from __future__ import annotations

import re

from app.extraction import association
from app.extraction.candidates import Candidate, ExtractionInput
from app.extraction.vocabulary import (
    ACKNOWLEDGEMENT,
    ALIASES,
    FIELD_CUE,
    NEGATABLE_KEYS,
    SHORT_NO,
    TREATMENT_FORM,
    TREATMENT_USE,
    UNKNOWN_CUE,
    alias_matches,
    clause_end,
    is_treatment_clause,
    negation_start,
    product_mentions,
)
from app.questions import QUESTION_KEYS

_SENTENCE = re.compile(r"[^.!?;]+[.!?;]?")
_NAME = re.compile(r"\b(?:called|named|brand\s+(?:was|is)|name\s+(?:was|is))\s+[\"'\u201c]?([A-Za-z][\w-]{2,40})")
_UNIT_KEYS = ("duration", "prior_treatment_duration")


class RuleCandidateProvider:
    mode = "fixture"

    def extract(self, data: ExtractionInput) -> list[Candidate]:
        out: list[Candidate] = []
        for turn in data.targets:
            text = turn.text
            if ACKNOWLEDGEMENT.match(text):
                continue
            question = data.questions.get(turn.turn_id)
            answers = QUESTION_KEYS.get(question.template_id, ()) if question else ()
            for sentence in _SENTENCE.finditer(text):
                out += self._sentence(turn.turn_id, text, sentence.start(), sentence.end(), answers)
            for value, verb_start, _, value_end in product_mentions(text):  # named product/medication use
                cue = negation_start(text, verb_start)
                out.append(Candidate(key="product_use", value=value,
                                     status="negated" if cue is not None else "reported", turn_id=turn.turn_id,
                                     quote=text[cue if cue is not None else verb_start:value_end]))
            for link in association.links(text):  # clause-level symptom–site statements only
                if not link.uncertain:
                    out.append(Candidate(key=association.KEY, value=link.value,
                                         status="negated" if link.negated else "reported",
                                         turn_id=turn.turn_id, quote=text[link.start:link.end]))
            if "exposure" in answers and SHORT_NO.match(text) and not any(c.key == "exposure" for c in out
                                                                          if c.turn_id == turn.turn_id):
                m = SHORT_NO.match(text)
                out.append(Candidate(key="exposure", value="no_new_product", turn_id=turn.turn_id,
                                     quote=text[m.start(1):m.end(1)]))
            unknown = UNKNOWN_CUE.search(text)
            if unknown:
                quote = text[unknown.start():clause_end(text, unknown.start())].strip()
                keys = [k for k, cue in FIELD_CUE.items() if cue.search(quote)]
                if "duration" in keys and "onset" in keys:
                    keys.remove("onset")  # "don't know when it began" is one unknown, not two
                if not keys:
                    keys = list(answers)
                for key in keys:
                    if key == "duration" and "duration" not in answers and "prior_treatment_duration" in answers:
                        key = "prior_treatment_duration"
                    if key == "prior_treatment_duration" and "prior_treatment_duration" not in answers \
                            and not TREATMENT_USE.search(text):
                        continue
                    out.append(Candidate(key=key, status="unknown", turn_id=turn.turn_id, quote=quote))
            name = _NAME.search(text)
            if name:
                out.append(Candidate(key="prior_treatment_name", value=name.group(1), turn_id=turn.turn_id,
                                     quote=text[name.start():name.end()]))
        return out

    def _sentence(self, turn_id: str, text: str, start: int, end: int, answers: tuple[str, ...]) -> list[Candidate]:
        sentence = text[start:end]
        answering_treatment = "prior_treatment_duration" in answers and "duration" not in answers
        sentence_about_treatment = bool(TREATMENT_USE.search(sentence) or TREATMENT_FORM.search(sentence))
        out: list[Candidate] = []
        for key in ALIASES:
            if key == "prior_treatment_response" and not (sentence_about_treatment or answering_treatment):
                continue
            for match in alias_matches(key, sentence):
                a, b = start + match.start, start + match.end
                if key in _UNIT_KEYS:
                    treatment = answering_treatment or is_treatment_clause(text, a, b)
                    if key != ("prior_treatment_duration" if treatment else "duration"):
                        continue
                cue = negation_start(text, a) if key in NEGATABLE_KEYS else None
                if cue is not None:
                    out.append(Candidate(key=key, value=match.value, status="negated", turn_id=turn_id,
                                         quote=text[cue:b]))
                else:
                    out.append(Candidate(key=key, value=match.value, turn_id=turn_id, quote=text[a:b]))
        return out
