"""Server validation of candidate facts, and assembly of validated patient facts.

A candidate survives only if: the key is allowed; it cites an ACTIVE PATIENT turn (agent turns are
never evidence); its quote is an exact substring of that turn; its value is the server alias value
for words inside the quote (or, for raw-value keys, words the patient actually said); and its
status is consistent with the words (negation needs a negation cue, unknown needs "don't know"-type
words about that field or an answer to a question about it). Everything else is rejected, never
repaired into a stronger claim: "cream" never becomes a drug name, "weeks" never becomes "three
weeks", "didn't help" stays the patient's reported response.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.extraction import association
from app.extraction.candidates import Candidate, ExtractionInput
from app.extraction.vocabulary import (
    ALIASES,
    ALLOWED_KEYS,
    FIELD_CUE,
    GENERIC_TREATMENT_WORDS,
    MULTI_VALUE_KEYS,
    NEG_CUE,
    NEGATABLE_KEYS,
    RAW_VALUE_KEYS,
    SHORT_NO,
    TREATMENT_FORM,
    TREATMENT_USE,
    UNKNOWN_CUE,
    alias_matches,
    canonical,
    is_treatment_clause,
    negated_in_context,
    product_value_supported,
)
from app.models import EvidenceRef, PatientFact, Turn
from app.questions import QUESTION_KEYS


@dataclass(frozen=True)
class Valid:
    key: str
    value: str | None
    status: str  # reported | negated | unknown
    turn: Turn
    quote: str


@dataclass(frozen=True)
class Rejected:
    candidate: Candidate
    reason: str


def _locate(turn: Turn, quote: str) -> tuple[int, str] | None:
    quote = quote.strip()
    if len(quote) < 2:
        return None
    i = turn.text.find(quote)
    if i < 0:
        i = turn.text.lower().find(quote.lower())  # same words, different capitalisation
    return (i, turn.text[i:i + len(quote)]) if i >= 0 else None


def _clause(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".;!?") + 1
    rights = [p for p in (text.find(c, end) for c in ".;!?") if p >= 0]
    return text[left:min(rights) if rights else len(text)]


def _treatment_context(turn: Turn, start: int, end: int, answers: tuple[str, ...]) -> bool:
    """Treatment sentence: needed for a reported treatment response ("I tried a cream, but it didn't help")."""
    sentence = _clause(turn.text, start, end)
    return bool(TREATMENT_USE.search(sentence) or TREATMENT_FORM.search(sentence)) or "prior_treatment_duration" in answers


def _treatment_duration(turn: Turn, start: int, end: int, answers: tuple[str, ...]) -> bool:
    """A duration belongs to a treatment only within the treatment's own clause (or as its answer)."""
    if "duration" in answers:
        return False
    return "prior_treatment_duration" in answers or is_treatment_clause(turn.text, start, end)


def validate(candidates: list[Candidate], data: ExtractionInput) -> tuple[list[Valid], list[Rejected]]:
    turns = {t.turn_id: t for t in data.patient_turns}
    valid: list[Valid] = []
    rejected: list[Rejected] = []
    seen: set[tuple] = set()

    def reject(c: Candidate, reason: str) -> None:
        rejected.append(Rejected(c, reason))

    for c in candidates:
        if c.key not in ALLOWED_KEYS:
            reject(c, "key_not_allowed")
            continue
        turn = turns.get(c.turn_id)
        if turn is None or turn.role != "patient":
            reject(c, "not_an_active_patient_turn")
            continue
        located = _locate(turn, c.quote)
        if located is None:
            reject(c, "quote_not_in_turn")
            continue
        start, quote = located
        end = start + len(quote)
        question = data.questions.get(turn.turn_id)
        answers = QUESTION_KEYS.get(question.template_id, ()) if question else ()

        if c.key == association.KEY:
            value = _association(c, turn, start, end)
            if isinstance(value, Rejected):
                rejected.append(value)
                continue
            item = (c.key, value, c.status, turn.turn_id, quote)
            if item not in seen:
                seen.add(item)
                valid.append(Valid(c.key, value, c.status, turn, quote))
            continue
        if c.status == "unknown":
            if not UNKNOWN_CUE.search(quote):
                reject(c, "unknown_without_unknown_words")
                continue
            cue = FIELD_CUE.get(c.key)
            if c.key not in answers and not (cue and cue.search(quote)):
                reject(c, "unknown_not_about_this_field")
                continue
            if c.key == "prior_treatment_duration" and c.key not in answers and not TREATMENT_USE.search(turn.text):
                reject(c, "treatment_detail_without_treatment_context")
                continue
            value: str | None = None
        else:
            value = _value(c, turn, start, end, quote, answers)
            if isinstance(value, Rejected):
                rejected.append(value)
                continue
        item = (c.key, value, c.status, turn.turn_id, quote)
        if item not in seen:
            seen.add(item)
            valid.append(Valid(c.key, value, c.status, turn, quote))
    return valid, rejected


def _association(c: Candidate, turn: Turn, start: int, end: int) -> str | Rejected:
    """A symptom–site association must be stated together inside its own quote (rule 1 of
    ``app.extraction.association``); "unknown" is not a supported status for it."""
    if c.status == "unknown":
        return Rejected(c, "association_status_not_supported")
    pair = association.split(c.value)
    if pair is None:
        return Rejected(c, "association_value_format")
    value = association.join(*pair)
    reason = association.supported(turn.text, start, end, value, c.status == "negated")
    return Rejected(c, reason) if reason else value


def answer_associations(valid: list[Valid], data: ExtractionInput) -> list[Valid]:
    """Rule 2 of ``app.extraction.association``: a direct answer to the site (or symptom) question
    links to the single symptom (or site) the patient reported elsewhere. Returns paired evidence
    items (the answer quote and the other quote) for each association; nothing when several
    symptoms or sites would make it a guess."""
    out: list[Valid] = []
    for turn_id, question in data.questions.items():
        asked = QUESTION_KEYS.get(question.template_id, ())
        if asked not in (("site",), ("symptom",)):
            continue
        answer_key, other_key = (("site", "symptom") if asked == ("site",) else ("symptom", "site"))
        answers = [v for v in valid if v.turn.turn_id == turn_id and v.key == answer_key and v.status == "reported"]
        others = [v for v in valid if v.turn.turn_id != turn_id and v.key == other_key]
        other_values = {v.value for v in others}
        if not answers or len(other_values) != 1 or any(v.status != "reported" for v in others):
            continue
        other = min(others, key=lambda v: (v.turn.sequence, v.turn.text.find(v.quote)))
        for a in answers:
            symptom, site = (other.value, a.value) if answer_key == "site" else (a.value, other.value)
            value = association.join(symptom, site)
            out += [Valid(association.KEY, value, "reported", other.turn, other.quote),
                    Valid(association.KEY, value, "reported", a.turn, a.quote)]
    return out


def _value(c: Candidate, turn: Turn, start: int, end: int, quote: str, answers: tuple[str, ...]) -> str | Rejected:
    proposed = canonical(c.value)
    if not proposed:
        return Rejected(c, "missing_value")
    if c.key == "prior_treatment_response" and not _treatment_context(turn, start, end, answers):
        return Rejected(c, "treatment_detail_without_treatment_context")
    if c.key == "prior_treatment_duration" and not _treatment_duration(turn, start, end, answers):
        return Rejected(c, "treatment_detail_without_treatment_context")
    if c.key == "duration" and _treatment_duration(turn, start, end, answers):
        return Rejected(c, "treatment_duration_is_not_symptom_duration")
    if c.status == "negated" and c.key not in NEGATABLE_KEYS:
        return Rejected(c, "negation_not_supported_for_key")

    matches = alias_matches(c.key, quote)
    if c.key == "exposure" and not matches and "exposure" in answers and SHORT_NO.match(turn.text) \
            and start == SHORT_NO.match(turn.text).start(1) and proposed == "no_new_product":
        return "no_new_product"  # bare "No" answering the product-change question, read only through it
    if matches:
        alias = next((m for m in matches if m.value == proposed), None)
        if alias is None:
            return Rejected(c, "value_not_supported_by_quote")
        if c.key in NEGATABLE_KEYS:
            negated = bool(NEG_CUE.search(quote[:alias.start])) or negated_in_context(turn.text, start + alias.start)
            if negated != (c.status == "negated"):
                return Rejected(c, "negation_mismatch")
        return alias.value
    if ALIASES.get(c.key) and c.key not in RAW_VALUE_KEYS:
        return Rejected(c, "value_not_supported_by_quote")
    if c.key not in RAW_VALUE_KEYS:
        return Rejected(c, "value_not_supported_by_quote")
    # Raw value: the patient's own words, verbatim inside the quote.
    raw = c.value.strip() if c.value else ""
    if not raw or raw.lower() not in quote.lower():
        return Rejected(c, "value_not_supported_by_quote")
    if c.key == "product_use":
        # The use verb may sit just before a minimal quote ("I used | minoxidil foam"), same sentence only.
        sentence_start = max(turn.text.rfind(ch, 0, start) for ch in ".;!?") + 1
        lead_in = turn.text[max(sentence_start, start - 30):end]
        if not (product_value_supported(quote, raw) or product_value_supported(lead_in, raw)):
            return Rejected(c, "product_use_without_use_words_or_name")
    if c.key == "prior_treatment_name":
        if raw.lower() in GENERIC_TREATMENT_WORDS or len(raw) < 3:
            return Rejected(c, "generic_word_is_not_a_name")
        if not (FIELD_CUE["prior_treatment_name"].search(quote) or "prior_treatment_name" in answers):
            return Rejected(c, "name_without_naming_words")
    if c.key in ("duration", "prior_treatment_duration") and not re.search(r"\b(day|week|month|year|since|ago)", raw, re.I):
        return Rejected(c, "value_not_a_duration")
    if c.key in NEGATABLE_KEYS:
        negated = bool(NEG_CUE.search(quote[:quote.lower().find(raw.lower())]))
        if negated != (c.status == "negated"):
            return Rejected(c, "negation_mismatch")
    return canonical(raw)


# ---------------------------------------------------------------- fact assembly

def _fact_id(key: str, tag: str) -> str:
    return f"F-{key}-{re.sub(r'[^a-z0-9_]+', '', tag)[:40]}"


def _refs(items: list[Valid]) -> list[EvidenceRef]:
    seen, out = set(), []
    for v in sorted(items, key=lambda v: (v.turn.sequence, v.turn.text.find(v.quote))):
        if (v.turn.turn_id, v.quote) not in seen:
            seen.add((v.turn.turn_id, v.quote))
            out.append(EvidenceRef(source_type="patient_turn", source_id=v.turn.turn_id, quote=v.quote))
    return out


def assemble_facts(valid: list[Valid]) -> list[PatientFact]:
    """Merge validated candidates into facts. Distinct explicit values are a conflict, never a guess.

    - multi-value keys (symptom, site, additional_symptoms): one fact per value; the same value both
      reported and denied is ``conflicting``.
    - single-value keys: one fact per key. A later explicit value replaces an earlier "don't know";
      two different explicit values (or a value and its denial) are ``conflicting``.
    """
    facts: list[PatientFact] = []
    order = {k: i for i, k in enumerate(ALLOWED_KEYS)}
    for key in sorted({v.key for v in valid}, key=order.get):
        items = [v for v in valid if v.key == key]
        if key in MULTI_VALUE_KEYS:
            for value in sorted({v.value for v in items if v.value}):
                group = [v for v in items if v.value == value]
                statuses = {v.status for v in group}
                status = "conflicting" if {"reported", "negated"} <= statuses else (
                    "negated" if statuses == {"negated"} else "reported")
                facts.append(PatientFact(fact_id=_fact_id(key, value), key=key,
                                         value=None if status == "conflicting" else value,
                                         status=status, evidence=_refs(group)))
            continue
        explicit = [v for v in items if v.status != "unknown"]
        if not explicit:
            facts.append(PatientFact(fact_id=_fact_id(key, "unknown"), key=key, value=None, status="unknown",
                                     evidence=_refs(items)))
            continue
        values = {(v.value, v.status) for v in explicit}
        if len(values) > 1:
            facts.append(PatientFact(fact_id=_fact_id(key, "conflict"), key=key, value=None, status="conflicting",
                                     evidence=_refs(explicit)))
            continue
        value, status = values.pop()
        facts.append(PatientFact(fact_id=_fact_id(key, value or status), key=key, value=value, status=status,
                                 evidence=_refs(explicit)))
    return facts
