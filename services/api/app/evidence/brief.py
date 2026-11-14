"""Doctor brief rendered from validated facts with fixed templates (no second free-form summary).

Every patient-derived item carries the exact quotes that support it. Missing details are listed as
``missing`` with no evidence; details the patient said they do not know are ``reported`` with the
patient's own "don't know" words; contradictions are ``conflicting`` with both quotes.
"""
from __future__ import annotations

import re

from app.extraction import association
from app.extraction.vocabulary import TREATMENT_FORM
from app.models import Brief, BriefItem, DoctorClarification, EvidenceRef, PatientFact, Question, Turn

_LABEL = {"site": "body site", "symptom": "symptom", "symptom_site": "symptom at a body site",
          "duration": "duration", "onset": "onset",
          "exposure": "product-change history", "product_use": "named product use",
          "prior_treatment_name": "treatment name",
          "prior_treatment_duration": "treatment duration", "prior_treatment_response": "treatment response",
          "additional_symptoms": "additional symptoms"}
_DURATION = {"few_days": "a few days", "days": "days", "weeks": "weeks", "months": "months", "years": "years"}
_RESPONSE = {"no_improvement": "no improvement", "improved": "improvement", "partial_improvement": "partial improvement",
             "worse": "worsening"}


def _h(value: str | None) -> str:
    return (value or "").replace("_", " ")


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def treatment_mention(turns: list[Turn]) -> tuple[str, EvidenceRef] | None:
    """First "a cream"-style mention in active patient turns: (form word, exact quote)."""
    for turn in turns:
        m = TREATMENT_FORM.search(turn.text)
        if m:
            return m.group(1).lower(), EvidenceRef(source_type="patient_turn", source_id=turn.turn_id,
                                                   quote=turn.text[m.start():m.end()])
    return None


def build_brief(revision: int, facts: list[PatientFact], turns: list[Turn], questions: list[Question],
                candidate_case_ids: list[str]) -> Brief:
    by_key: dict[str, list[PatientFact]] = {}
    for f in facts:
        by_key.setdefault(f.key, []).append(f)

    def reported(key: str) -> list[PatientFact]:
        return [f for f in by_key.get(key, []) if f.status == "reported" and f.value]

    summary: list[BriefItem] = []
    sites, symptoms = reported("site"), reported("symptom")
    # A symptom is placed at a site only where the patient stated them together (symptom_site);
    # separate mentions are listed separately, never combined into "X on the Y".
    pairs = reported(association.KEY)
    for f in pairs:
        summary.append(BriefItem(text=f"Patient reports {association.human(f.value)}.", status="reported",
                                 evidence=f.evidence))
    paired = [association.split(f.value) for f in pairs]
    loose_symptoms = [f for f in symptoms if all(p is None or p[0] != f.value for p in paired)]
    loose_sites = [f for f in sites if all(p is None or p[1] != f.value for p in paired)]
    if loose_symptoms:
        summary.append(BriefItem(
            text=f"Patient reports {_join([_h(f.value) for f in loose_symptoms])} "
                 "(body site not clearly linked in the patient's words).",
            status="reported", evidence=[e for f in loose_symptoms for e in f.evidence[:1]]))
    if loose_sites:
        summary.append(BriefItem(
            text=f"Patient mentions the {_join([_h(f.value) for f in loose_sites])} "
                 "(not clearly linked to a symptom in the patient's words).",
            status="reported", evidence=[e for f in loose_sites for e in f.evidence[:1]]))
    for f in [f for k in ("symptom", "site", "additional_symptoms") for f in by_key.get(k, []) if f.status == "negated"]:
        summary.append(BriefItem(text=f"Patient denies {_h(f.value)} ({_LABEL[f.key]}).", status="reported",
                                 evidence=f.evidence))
    for f in [f for f in by_key.get(association.KEY, []) if f.status == "negated"]:
        summary.append(BriefItem(text=f"Patient denies {association.human(f.value)}.", status="reported",
                                 evidence=f.evidence))
    for f in reported("additional_symptoms"):
        summary.append(BriefItem(text=f"Patient also mentions: {_h(f.value)}.", status="reported", evidence=f.evidence))

    timeline: list[BriefItem] = []
    for f in reported("duration"):
        timeline.append(BriefItem(text=f"Patient describes the duration as {_DURATION.get(f.value, _h(f.value))}.",
                                  status="reported", evidence=f.evidence))
    for f in reported("onset"):
        timeline.append(BriefItem(text=f"Patient describes the onset as: {_h(f.value)}.", status="reported",
                                  evidence=f.evidence))
    for f in reported("exposure"):
        text = ("Patient reports starting a new product before the symptoms." if f.value == "new_product" else
                "Patient reports no new products before the symptoms." if f.value == "no_new_product" else
                f"Patient reports a product or activity change: {_h(f.value)}.")
        timeline.append(BriefItem(text=text, status="reported", evidence=f.evidence))
    # Named product/medication use: context only, in the patient's words. No purpose, timing, cause or response.
    for f in reported("product_use"):
        timeline.append(BriefItem(text=f"Patient mentions using {_h(f.value)}.", status="reported",
                                  evidence=f.evidence))
    for f in [f for f in by_key.get("product_use", []) if f.status == "negated"]:
        timeline.append(BriefItem(text=f"Patient says they did not use {_h(f.value)}.", status="reported",
                                  evidence=f.evidence))

    treatment: list[BriefItem] = []
    mention = treatment_mention(turns)
    names, durations, responses = reported("prior_treatment_name"), reported("prior_treatment_duration"), \
        reported("prior_treatment_response")
    if mention or names or durations or responses:
        form = mention[0] if mention else "treatment"
        subject = f"a {form} named {names[0].value}" if names else f"an unnamed {form}" if form[0] in "aeiou" \
            else f"a {form} (name not given)"
        parts = [f"Patient reports trying {subject}"]
        if durations:
            parts.append(f"used for {_DURATION.get(durations[0].value, _h(durations[0].value))}")
        text = ", ".join(parts)
        if responses:
            text += f", with {_RESPONSE.get(responses[0].value, _h(responses[0].value))} reported by the patient"
        evidence = ([mention[1]] if mention else []) + [e for f in names + durations + responses for e in f.evidence[:1]]
        treatment.append(BriefItem(text=text + ".", status="reported", evidence=evidence))

    unresolved: list[BriefItem] = []
    for f in facts:
        if f.status == "unknown":
            unresolved.append(BriefItem(text=f"{_LABEL[f.key].capitalize()}: patient does not know.", status="reported",
                                        evidence=f.evidence))
        elif f.status == "conflicting":
            unresolved.append(BriefItem(text=f"Conflicting details about the {_LABEL[f.key]}.", status="conflicting",
                                        evidence=f.evidence))
    if mention and not by_key.get("prior_treatment_name"):
        unresolved.append(BriefItem(text=f"{mention[0].capitalize()} name not provided.", status="missing", evidence=[]))
    for key in ("site", "symptom", "duration"):
        if key not in by_key and not (key == "duration" and "onset" in by_key):
            unresolved.append(BriefItem(text=f"{_LABEL[key].capitalize()} not provided.", status="missing", evidence=[]))
    for q in questions:
        if q.status == "skipped" and q.kind == "intake_gap":
            # Skipped is recorded as skipped: never as a "no" or as an absent detail.
            unresolved.append(BriefItem(text=f"Clarification skipped by the patient: {q.text}", status="missing",
                                        evidence=[]))
        if q.status in ("skipped", "unknown") and q.kind == "case_difference":
            unresolved.append(BriefItem(text=f"Clarification {'skipped' if q.status == 'skipped' else 'not known'}: "
                                        f"{q.text}", status="missing", evidence=[]))

    clarify: list[DoctorClarification] = []
    if mention or responses:
        clarify.append(DoctorClarification(
            text=f"Clarify the reported prior {mention[0] if mention else 'treatment'} and whether it is relevant to the assessment.",
            basis_fact_ids=[f.fact_id for f in names + durations + responses + by_key.get("prior_treatment_name", [])][:4],
            basis_case_ids=[]))
    for f in facts:
        if f.status == "conflicting":
            clarify.append(DoctorClarification(text=f"Clarify the {_LABEL[f.key]}: the patient gave differing details.",
                                               basis_fact_ids=[f.fact_id], basis_case_ids=[]))
        elif f.status == "unknown" and f.key in ("duration", "onset", "exposure"):
            clarify.append(DoctorClarification(text=f"Clarify the {_LABEL[f.key]} during assessment; the patient did not know.",
                                               basis_fact_ids=[f.fact_id], basis_case_ids=[]))
    for q in questions:
        if q.kind == "case_difference" and q.status in ("skipped", "unknown") and q.comparison_basis:
            clarify.append(DoctorClarification(
                text=f"Fictional cases differ on {_LABEL.get(q.comparison_basis.contrasting_feature, 'a detail')}; "
                     "the patient did not answer this during intake.",
                basis_fact_ids=[], basis_case_ids=q.comparison_basis.case_ids))
    if not clarify and symptoms and not candidate_case_ids:
        clarify.append(DoctorClarification(text="Clarify the symptom during clinical assessment.",
                                           basis_fact_ids=[symptoms[0].fact_id], basis_case_ids=[]))
    return Brief(patient_revision=revision, summary_items=summary, timeline_items=timeline,
                 prior_treatment_items=treatment, unresolved_items=unresolved, doctor_clarifications=clarify)


_ = re  # kept for future template use
