"""Validation for the published (real-article) case collection.

Published records come from original open-access PMC articles via
``data/tools/build_published_candidates.py``. They start ``source_review.status = "pending"``.
Only records a human source reviewer has marked ``reviewed`` (with reviewer and time) may be
imported. Nothing here marks a record reviewed, and clinical review is never inferred.

Checks on top of the DTO schema: case ID uniqueness, published kind and collection ID, passage
ownership and hashes, quote substrings inside the same case's passages, an original PMC article
URL matching the record's PMCID, and a Creative Commons licence string. The collection version
is the same content digest the synthetic fixtures use, so any edit yields a new version.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.extraction import association
from app.models import CaseRecord, Collection

PUBLISHED_PREFIX = "published-"
_PMC_URL = re.compile(r"^https://pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)/$")


class PublishedRecordError(ValueError):
    pass


def collection_digest(raw_cases: list[dict]) -> str:
    return hashlib.sha256(json.dumps(raw_cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_record(raw: dict, collection_id: str, *, require_reviewed: bool) -> CaseRecord:
    try:
        case = CaseRecord.model_validate(raw)
    except ValidationError as exc:
        raise PublishedRecordError(f"{raw.get('case_id', '?')}: schema validation failed ({exc.error_count()} errors)") from exc
    cid = case.case_id
    if case.source_kind != "published":
        raise PublishedRecordError(f"{cid}: source_kind must be 'published'")
    if case.collection_id != collection_id:
        raise PublishedRecordError(f"{cid}: belongs to {case.collection_id!r}, not {collection_id!r}")
    url = _PMC_URL.match(case.article_url or "")
    if not url or case.article_identifiers.get("pmcid") != url.group(1):
        raise PublishedRecordError(f"{cid}: article_url must be the original PMC article of its PMCID")
    if not case.license.startswith("CC "):
        raise PublishedRecordError(f"{cid}: licence must be a verified Creative Commons licence")
    affirmed = {(f.key, f.value) for f in case.features if f.polarity == "affirmed"}
    pairs = [f for f in case.features if f.key == association.KEY]
    if not pairs:
        raise PublishedRecordError(f"{cid}: at least one explicit symptom_site association is required")
    for f in pairs:
        parts = association.split(f.value)
        if parts is None or f.value != association.join(*parts):
            raise PublishedRecordError(f"{cid}: symptom_site value {f.value!r} is not '<symptom>@<site>'")
        if f.polarity == "affirmed" and not {("symptom", parts[0]), ("site", parts[1])} <= affirmed:
            raise PublishedRecordError(f"{cid}: symptom_site {f.value!r} needs matching affirmed symptom and site")
    cite = case.citation
    if cite is None or not cite.authors or not cite.journal.strip() or not cite.year.strip():
        raise PublishedRecordError(f"{cid}: citation metadata (authors, journal, year) is required")
    if not cite.license_url.startswith("https://creativecommons.org/licenses/") \
            or case.license != f"{cite.license_name} ({cite.license_url})":
        raise PublishedRecordError(f"{cid}: licence fields disagree with the citation licence")
    review = case.source_review
    if require_reviewed and not (review.status == "reviewed" and (review.reviewer or "").strip() and review.reviewed_at):
        raise PublishedRecordError(f"{cid}: source review is {review.status!r}; only reviewed records may be imported")
    if review.status == "fixture_checked":
        raise PublishedRecordError(f"{cid}: 'fixture_checked' is for synthetic fixtures only")
    if not case.passages:
        raise PublishedRecordError(f"{cid}: no passages")
    own: dict[str, str] = {}
    for p in case.passages:
        if p.case_id != cid:
            raise PublishedRecordError(f"{cid}: passage {p.passage_id} belongs to another case")
        if hashlib.sha256(p.text.encode()).hexdigest() != p.sha256:
            raise PublishedRecordError(f"{cid}: passage {p.passage_id} hash mismatch")
        if p.passage_id in own:
            raise PublishedRecordError(f"{cid}: duplicate passage {p.passage_id}")
        own[p.passage_id] = p.text
    statements = [*case.features, *case.actions, *case.outcomes]
    for item in statements:
        if not item.evidence:
            raise PublishedRecordError(f"{cid}: statement without evidence")
        for ref in item.evidence:
            if ref.source_type != "case_passage" or ref.source_id not in own or ref.quote not in own[ref.source_id]:
                raise PublishedRecordError(f"{cid}: evidence {ref.source_id!r} is not a quote from this case's passages")
    return case


def build_collection(raw_cases: list[dict], collection_id: str, *, require_reviewed: bool = True
                     ) -> tuple[Collection, list[CaseRecord]]:
    if not collection_id.startswith(PUBLISHED_PREFIX):
        raise PublishedRecordError(f"published collection IDs start with {PUBLISHED_PREFIX!r}")
    if not raw_cases:
        raise PublishedRecordError("no records to import")
    raw_cases = sorted(raw_cases, key=lambda r: r.get("case_id", ""))
    cases = [validate_record(r, collection_id, require_reviewed=require_reviewed) for r in raw_cases]
    ids = [c.case_id for c in cases]
    if len(set(ids)) != len(ids):
        raise PublishedRecordError("duplicate case IDs")
    passage_ids = [p.passage_id for c in cases for p in c.passages]
    if len(set(passage_ids)) != len(passage_ids):
        raise PublishedRecordError("a passage ID is used by more than one case")
    collection = Collection(
        collection_id=collection_id, mode="published", version=collection_digest(raw_cases),
        case_count=len(cases), source_review_count=sum(c.source_review.status == "reviewed" for c in cases),
        clinical_reviewed=all(c.clinical_reviewed for c in cases),
    )
    return collection, cases


def read_records(directory: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("PUB-*.json"))]
