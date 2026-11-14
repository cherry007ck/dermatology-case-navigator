"""Load and validate the shared fictional fixtures.

Every fixture is parsed through the Pydantic DTOs (unknown fields rejected) and
checked for passage hashes, case ownership, quote substrings and the collection
hash. A failure raises at startup rather than serving unvalidated data.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import AdvanceResult, CaseRecord, Collection, SessionSnapshot


class FixtureError(RuntimeError):
    pass


@dataclass(frozen=True)
class FixtureBundle:
    collection: Collection
    cases: list[CaseRecord]
    # Fixture AdvanceResults keyed by file stem, e.g. "after-initial".
    advance_examples: dict[str, AdvanceResult]
    confirmed_example: SessionSnapshot


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"Cannot read fixture {path.name}") from exc


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _check_cases(raw_cases: list[dict], collection: Collection) -> None:
    seen: set[str] = set()
    for case in raw_cases:
        if case["case_id"] in seen:
            raise FixtureError(f"Duplicate case {case['case_id']}")
        seen.add(case["case_id"])
        if case["source_kind"] == "synthetic" and (case["article_url"] or case["article_identifiers"]):
            raise FixtureError(f"Synthetic case {case['case_id']} has article provenance")
        own: dict[str, str] = {}
        for passage in case["passages"]:
            if passage["case_id"] != case["case_id"]:
                raise FixtureError(f"Passage {passage['passage_id']} belongs to another case")
            if hashlib.sha256(passage["text"].encode()).hexdigest() != passage["sha256"]:
                raise FixtureError(f"Passage {passage['passage_id']} hash mismatch")
            own[passage["passage_id"]] = passage["text"]
        for node in _walk(case):
            for ref in node.get("evidence", []):
                if ref["source_id"] not in own or ref["quote"] not in own[ref["source_id"]]:
                    raise FixtureError(f"Unsupported evidence in case {case['case_id']}")
    digest = hashlib.sha256(json.dumps(raw_cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if digest != collection.version or collection.case_count != len(raw_cases):
        raise FixtureError("Collection version/count does not match cases.json")


def load_fixture_bundle(root: Path) -> FixtureBundle:
    raw_cases = _read(root / "data/synthetic/cases.json")
    collection = Collection.model_validate(_read(root / "data/synthetic/collection.json"))
    _check_cases(raw_cases, collection)
    cases = [CaseRecord.model_validate(case) for case in raw_cases]

    examples_dir = root / "contracts/examples"
    advance_examples = {
        name: AdvanceResult.model_validate(_read(examples_dir / f"{name}.json"))
        for name in ("after-initial", "after-cream-answer", "after-exposure-answer", "no-match")
    }
    confirmed = SessionSnapshot.model_validate(_read(examples_dir / "confirmed-session.json"))
    return FixtureBundle(collection, cases, advance_examples, confirmed)


@lru_cache
def get_fixture_bundle() -> FixtureBundle:
    return load_fixture_bundle(get_settings().fixture_root)
