"""Deterministic case ranking ``structured-v2`` (docs/data/ranking-structured-v2.md).

Prototype engineering rules, not a validated clinical scoring system. Pure function of
(validated patient facts, stored cases, collection): the same immutable inputs always give the
same order, exclusions, score components and reasons. Nothing here reads a scenario name or a
turn count, and no language model is involved.

Change from ``structured-v1``. v1 intersected sites and symptoms independently, so scalp itching
plus facial swelling in one case counted as "facial itching". v2 needs a shared symptom AT a
shared site: a ``symptom_site`` association that both the patient and the case state explicitly,
with evidence for the association itself. Searches stored as ``structured-v1`` keep their stored
result and label. They are never recomputed, and a later v2 search marks its changes as caused by
the rule change.

1. Only cases of the selected collection's kind whose source review allows use. Published cases
   also need an article URL. Synthetic and published never mix.
2. Site gate (unchanged): an explicitly different documented site excludes (``site_conflict``);
   no shared site gives ``no_shared_site``; no shared symptom gives ``no_shared_symptom``.
3. A directly contradictory categorical exposure value excludes (``exposure_conflict``).
   Unmentioned information never creates a contradiction.
4. Association gate: at least one reported patient ``symptom_site`` equals an affirmed case
   ``symptom_site``. Separate mentions, negated, uncertain or conflicting associations never
   qualify. Otherwise ``no_shared_symptom``, with the reason text "no symptom explicitly reported
   at the same site in both".
5. Score: shared association site +3 and symptom +3 (the association establishes both), same
   qualitative duration +1, same exposure value +2. At most three cards, score descending then
   ``case_id``.

Case associations: published records carry explicit, human-reviewed ``symptom_site`` features.
Synthetic fixture records written before the key existed (``synthetic-demo-v1``) have none, so
association rule 1 is applied to their own passages. Only pairs of the case's own affirmed symptom
and site values count, and each pair is quoted from the passage text that states them together.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.extraction import association
from app.extraction.vocabulary import EXPOSURE_GATE_VALUES
from app.models import (
    CaseAttribution,
    CaseCard,
    CaseChange,
    CaseRecord,
    Collection,
    EvidenceRef,
    ExcludedCase,
    Passage,
    PatientFact,
    ScoreComponents,
    SearchVersion,
    SupportedStatement,
)

ALGORITHM_VERSION = "structured-v2"
MAX_CARDS = 3
WEIGHTS = {"site": 3, "symptom": 3, "duration": 1, "exposure": 2}
_LABEL = {"new_product": "new-product history", "no_new_product": "no-new-product history"}
ASSOC = association.KEY


def _human(value: str) -> str:
    return _LABEL.get(value, value.replace("_", " "))


@dataclass
class _Case:
    record: CaseRecord
    passages: dict[str, Passage]
    affirmed: dict[str, dict[str, list[EvidenceRef]]] = field(default_factory=dict)
    invalid: int = 0
    derived_associations: bool = False


def _valid_ref(ref: EvidenceRef, case: CaseRecord, passages: dict[str, Passage]) -> bool:
    passage = passages.get(ref.source_id)
    return (ref.source_type == "case_passage" and passage is not None and passage.case_id == case.case_id
            and ref.quote in passage.text)


def _prepare(case: CaseRecord) -> _Case:
    passages = {p.passage_id: p for p in case.passages if p.case_id == case.case_id}
    prepared = _Case(case, passages)
    for feature in case.features:
        if not feature.evidence or not all(_valid_ref(r, case, passages) for r in feature.evidence):
            prepared.invalid += 1  # withheld: a feature without same-case passage support is ignored
            continue
        if feature.key == ASSOC and association.split(feature.value) is None:
            prepared.invalid += 1
            continue
        if feature.polarity == "affirmed":
            prepared.affirmed.setdefault(feature.key, {}).setdefault(feature.value, []).extend(feature.evidence)
    if case.source_kind == "synthetic" and not any(f.key == ASSOC for f in case.features):
        _derive_associations(prepared)
    return prepared


def _derive_associations(case: _Case) -> None:
    """Legacy synthetic records only: clause-level links stated in the case's own passages,
    restricted to the case's own affirmed symptom and site values."""
    symptoms = set(case.affirmed.get("symptom", {}))
    sites = set(case.affirmed.get("site", {}))
    for passage in sorted(case.passages.values(), key=lambda p: p.passage_id):
        for link in association.links(passage.text):
            if link.negated or link.uncertain or link.symptom not in symptoms or link.site not in sites:
                continue
            ref = EvidenceRef(source_type="case_passage", source_id=passage.passage_id,
                              quote=passage.text[link.start:link.end])
            case.affirmed.setdefault(ASSOC, {}).setdefault(link.value, []).append(ref)
            case.derived_associations = True


def _supported(statements: list[SupportedStatement], case: _Case) -> list[SupportedStatement]:
    """Case actions/outcomes shown only with valid same-case passage evidence."""
    return [s for s in statements if s.evidence and all(_valid_ref(r, case.record, case.passages) for r in s.evidence)]


@dataclass(frozen=True)
class PatientProfile:
    sites: dict[str, list[EvidenceRef]]
    symptoms: dict[str, list[EvidenceRef]]
    associations: dict[str, list[EvidenceRef]]
    denied_associations: dict[str, list[EvidenceRef]]
    duration: tuple[str, list[EvidenceRef]] | None
    exposure: tuple[str, list[EvidenceRef]] | None
    conflicting: list[PatientFact]

    @classmethod
    def from_facts(cls, facts: list[PatientFact]) -> PatientProfile:
        reported = [f for f in facts if f.status == "reported" and f.value]

        def single(key: str) -> tuple[str, list[EvidenceRef]] | None:
            f = next((f for f in reported if f.key == key), None)
            return (f.value, f.evidence) if f else None

        exposure = single("exposure")
        return cls(
            sites={f.value: f.evidence for f in reported if f.key == "site"},
            symptoms={f.value: f.evidence for f in reported if f.key == "symptom"},
            associations={f.value: f.evidence for f in reported if f.key == ASSOC},
            denied_associations={f.value: f.evidence for f in facts if f.key == ASSOC and f.status == "negated"
                                 and f.value},
            duration=single("duration"),
            exposure=exposure if exposure and exposure[0] in EXPOSURE_GATE_VALUES else None,
            conflicting=[f for f in facts if f.status == "conflicting" and f.key in ("site", "symptom", ASSOC, "exposure")],
        )


@dataclass(frozen=True)
class Ranked:
    case: _Case
    score: ScoreComponents
    shared: list[SupportedStatement]
    differences: list[SupportedStatement]
    by_feature: dict[str, SupportedStatement] = field(default_factory=dict)  # duration / exposure statements


def _first(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    return refs[:1]


def rank(facts: list[PatientFact], cases: list[CaseRecord], collection: Collection
         ) -> tuple[list[Ranked], list[ExcludedCase], str | None]:
    patient = PatientProfile.from_facts(facts)
    eligible: list[Ranked] = []
    excluded: list[ExcludedCase] = []
    for record in sorted(cases, key=lambda c: c.case_id):
        if record.source_kind != collection.mode or record.collection_id != collection.collection_id:
            excluded.append(ExcludedCase(case_id=record.case_id, reason="source_mode_mismatch", evidence=[]))
            continue
        review_ok = record.source_review.status == "reviewed" or (
            record.source_kind == "synthetic" and record.source_review.status == "fixture_checked")
        if not review_ok or (record.source_kind == "published" and not record.article_url):
            excluded.append(ExcludedCase(case_id=record.case_id, reason="unreviewed_source", evidence=[]))
            continue
        case = _prepare(record)
        if not case.affirmed:
            excluded.append(ExcludedCase(case_id=record.case_id, reason="invalid_evidence", evidence=[]))
            continue
        result = _assess(patient, case)
        if isinstance(result, ExcludedCase):
            excluded.append(result)
        else:
            eligible.append(result)
    eligible.sort(key=lambda r: (-r.score.total, r.case.record.case_id))
    eligible = eligible[:MAX_CARDS]
    no_match = None
    if not eligible:
        if not patient.sites or not patient.symptoms or not patient.associations:
            # Without a symptom stated at a site, the comparison basis is missing, not absent.
            no_match = "conflicting_details" if patient.conflicting else "insufficient_information"
        else:
            no_match = "no_comparable_cases"
    return eligible, excluded, no_match


def _assess(patient: PatientProfile, case: _Case) -> Ranked | ExcludedCase:
    case_id = case.record.case_id
    case_sites = case.affirmed.get("site", {})
    case_symptoms = case.affirmed.get("symptom", {})
    shared_sites = sorted(set(patient.sites) & set(case_sites))
    if not shared_sites:
        if patient.sites and case_sites:
            p, c = sorted(patient.sites)[0], sorted(case_sites)[0]
            return ExcludedCase(case_id=case_id, reason="site_conflict",
                                evidence=_first(patient.sites[p]) + _first(case_sites[c]))
        return ExcludedCase(case_id=case_id, reason="no_shared_site", evidence=[])
    case_assoc = case.affirmed.get(ASSOC, {})
    denied = sorted(set(patient.denied_associations) & set(case_assoc))
    denial = (_first(patient.denied_associations[denied[0]]) + _first(case_assoc[denied[0]])) if denied else []
    if not set(patient.symptoms) & set(case_symptoms):
        return ExcludedCase(case_id=case_id, reason="no_shared_symptom", evidence=denial)
    case_exposure = {v: refs for v, refs in case.affirmed.get("exposure", {}).items() if v in EXPOSURE_GATE_VALUES}
    if patient.exposure and case_exposure and patient.exposure[0] not in case_exposure:
        other = sorted(case_exposure)[0]
        return ExcludedCase(case_id=case_id, reason="exposure_conflict",
                            evidence=_first(patient.exposure[1]) + _first(case_exposure[other]))
    shared_assoc = sorted(set(patient.associations) & set(case_assoc))
    if not shared_assoc:
        # Sites and symptoms overlap only as separate mentions: not a supported match.
        return ExcludedCase(case_id=case_id, reason="no_shared_symptom", evidence=denial)

    shared: list[SupportedStatement] = []
    by_feature: dict[str, SupportedStatement] = {}
    for value in shared_assoc:
        shared.append(SupportedStatement(
            text=f"Shared reported symptom at the same site: {association.human(value)}.",
            evidence=_first(patient.associations[value]) + _first(case_assoc[value])))
    differences: list[SupportedStatement] = []
    case_duration = case.affirmed.get("duration", {})
    duration_shared = bool(patient.duration and patient.duration[0] in case_duration)
    if duration_shared:
        value = patient.duration[0]
        shared.append(SupportedStatement(text=f"Shared qualitative duration: {_human(value)}.",
                                         evidence=_first(patient.duration[1]) + _first(case_duration[value])))
        by_feature["duration"] = shared[-1]
    elif patient.duration and case_duration:
        other = sorted(case_duration)[0]
        differences.append(SupportedStatement(
            text=f"Duration differs: patient reports {_human(patient.duration[0])}; this case documents {_human(other)}.",
            evidence=_first(patient.duration[1]) + _first(case_duration[other])))
    exposure_shared = bool(patient.exposure and patient.exposure[0] in case_exposure)
    if exposure_shared:
        value = patient.exposure[0]
        shared.append(SupportedStatement(text=f"Shared explicit {_human(value)}.",
                                         evidence=_first(patient.exposure[1]) + _first(case_exposure[value])))
        by_feature["exposure"] = shared[-1]
    elif case_exposure and not patient.exposure:
        other = sorted(case_exposure)[0]
        differences.append(SupportedStatement(
            text="Patient product-change history is not yet known; this case documents an explicit value.",
            evidence=_first(case_exposure[other])))
    score = ScoreComponents(
        case_id=case_id, shared_site=WEIGHTS["site"], shared_symptom=WEIGHTS["symptom"],
        shared_duration=WEIGHTS["duration"] if duration_shared else 0,
        shared_exposure=WEIGHTS["exposure"] if exposure_shared else 0, total=0,
    )
    score = score.model_copy(update={"total": score.shared_site + score.shared_symptom + score.shared_duration
                                     + score.shared_exposure})
    return Ranked(case, score, shared, differences, by_feature)


def card(ranked: Ranked) -> CaseCard:
    record = ranked.case.record
    statements = [*ranked.shared, *ranked.differences, *_supported(record.actions, ranked.case),
                  *_supported(record.outcomes, ranked.case)]
    used = {r.source_id for s in statements for r in s.evidence if r.source_type == "case_passage"}
    return CaseCard(
        case_id=record.case_id, source_kind=record.source_kind, title=record.title,
        article_url=record.article_url if record.source_kind == "published" else None,
        shared_features=ranked.shared, important_differences=ranked.differences,
        actions=_supported(record.actions, ranked.case), outcomes=_supported(record.outcomes, ranked.case),
        passages=[p for p in record.passages if p.passage_id in used],
        attribution=attribution(record),
    )


def attribution(record: CaseRecord) -> CaseAttribution | None:
    """Attribution for a reviewed published case, from its stored source metadata only.
    Synthetic cases, and published records without captured citation metadata, get none."""
    cite = record.citation
    ids = record.article_identifiers
    if record.source_kind != "published" or cite is None or not ids.get("pmcid") \
            or record.source_review.status != "reviewed":
        return None
    return CaseAttribution(
        authors=list(cite.authors), journal=cite.journal, year=cite.year,
        doi=ids.get("doi"), pmid=ids.get("pmid"), pmcid=ids["pmcid"],
        license_name=cite.license_name, license_url=cite.license_url,
        source_review_status="reviewed", clinical_reviewed=record.clinical_reviewed,
    )


_EXCLUSION_REASON = {
    "site_conflict": "This case documents a different body site.",
    "exposure_conflict": "The patient's explicit product-change history contradicts this case's explicit history.",
    "no_shared_symptom": "No symptom is explicitly reported at the same body site in both.",
    "no_shared_site": "No explicitly shared body site.",
    "unreviewed_source": "Source not reviewed.",
    "source_mode_mismatch": "Different collection kind.",
    "invalid_evidence": "Case evidence failed validation.",
}
_RULE_CHANGE = f"Comparison rules changed to {ALGORITHM_VERSION} (symptom and site must be stated together)"


def _shared_reason(r: Ranked) -> str:
    extra = [label for label, n in (("qualitative duration", r.score.shared_duration),
                                    ("explicit exposure history", r.score.shared_exposure)) if n]
    if not extra:
        return "Shared explicit symptom at the same site."
    return (f"Shared explicit symptom at the same site; {' and '.join(extra)} also "
            f"{'matches' if len(extra) == 1 else 'match'}.")


def _gained(r: Ranked, old: ScoreComponents | None) -> list[SupportedStatement]:
    """Shared-feature statements that newly count towards this case's score."""
    out = []
    for feature, field_name in (("duration", "shared_duration"), ("exposure", "shared_exposure")):
        if getattr(r.score, field_name) and not (old and getattr(old, field_name)) and feature in r.by_feature:
            out.append(r.by_feature[feature])
    return out


def diff(previous: SearchVersion | None, ranked: list[Ranked], excluded: list[ExcludedCase]) -> list[CaseChange]:
    """Changes between the previous stored search and this one, from actual ranks and scores.
    Against a search stored under another algorithm version, changes are attributed to the rule
    change, never to new patient details."""
    before = {cid: i + 1 for i, cid in enumerate(previous.ranked_case_ids)} if previous else {}
    before_scores = {s.case_id: s for s in previous.score_components} if previous else {}
    rule_change = previous is not None and previous.algorithm_version != ALGORITHM_VERSION
    after = {r.case.record.case_id: (i + 1, r) for i, r in enumerate(ranked)}
    exclusions = {e.case_id: e for e in excluded}
    changes: list[CaseChange] = []
    for cid in sorted(set(before) | set(after), key=lambda c: (after.get(c, (99,))[0], before.get(c, 99), c)):
        if cid in after:
            rank_now, r = after[cid]
            evidence = [e for s in r.shared for e in s.evidence][:4]
            if cid not in before:
                reason = f"{_RULE_CHANGE}: {_shared_reason(r)}" if rule_change else _shared_reason(r)
                changes.append(CaseChange(case_id=cid, change="appeared", from_rank=None, to_rank=rank_now,
                                          reason=reason, evidence=evidence[:2]))
                continue
            moved = before[cid] != rank_now
            if rule_change:
                changes.append(CaseChange(case_id=cid, change="moved" if moved else "unchanged",
                                          from_rank=before[cid], to_rank=rank_now,
                                          reason=f"{_RULE_CHANGE}; still eligible: {_shared_reason(r)}",
                                          evidence=evidence[:2]))
                continue
            gained = _gained(r, before_scores.get(cid))
            parts = []
            if gained:
                text = gained[0].text[:-1]
                parts.append(f"{text[0].lower()}{text[1:]} now adds to the comparison")
            if moved:
                gone = [c for c in before if c not in after and before[c] < before[cid]]
                if gone:
                    parts.append(f"moved up because {', '.join(sorted(gone))} no longer qualifies")
            reason = ("Still eligible; " + "; ".join(parts) + ".") if parts else \
                "Still eligible; the new details do not change this case's shared features."
            changes.append(CaseChange(case_id=cid, change="moved" if moved else "unchanged",
                                      from_rank=before[cid], to_rank=rank_now, reason=reason,
                                      evidence=[e for s in gained for e in s.evidence]))
        else:
            ex = exclusions.get(cid)
            text = _EXCLUSION_REASON[ex.reason] if ex else "No longer among the top cases."
            changes.append(CaseChange(case_id=cid, change="removed", from_rank=before[cid], to_rank=None,
                                      reason=f"{_RULE_CHANGE}: {text}" if rule_change else text,
                                      evidence=ex.evidence if ex else []))
    return changes


def search_id(session_id: str, patient_revision: int, collection: Collection, facts: list[PatientFact]) -> str:
    """Reproducible ID from the exact immutable inputs."""
    payload = json.dumps({
        "session": session_id, "revision": patient_revision, "algorithm": ALGORITHM_VERSION,
        "collection": collection.collection_id, "collection_version": collection.version,
        "facts": [f.model_dump(mode="json") for f in facts],
    }, sort_keys=True)
    return f"SV-{patient_revision}-{hashlib.sha256(payload.encode()).hexdigest()[:20]}"
