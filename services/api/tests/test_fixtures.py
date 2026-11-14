from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.config import REPO_ROOT
from app.fixtures import FixtureError, load_fixture_bundle


def test_bundle_loads_and_is_synthetic_only() -> None:
    bundle = load_fixture_bundle(REPO_ROOT)
    assert bundle.collection.mode == "synthetic"
    assert bundle.collection.clinical_reviewed is False
    assert {c.case_id for c in bundle.cases} == {"SYN-A", "SYN-B", "SYN-C"}
    for case in bundle.cases:
        assert case.article_url is None and case.article_identifiers == {}


def _copy_root(tmp_path: Path) -> Path:
    for rel in ("data/synthetic", "contracts/examples"):
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel)
    return tmp_path


def _mutate_cases(root: Path, mutate) -> None:
    path = root / "data/synthetic/cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    mutate(cases)
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")


def test_rejects_quote_from_another_case(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)

    def wrong_case(cases):
        cases[0]["actions"][0]["evidence"][0]["source_id"] = "SYN-B-P2"

    _mutate_cases(root, wrong_case)
    with pytest.raises(FixtureError):
        load_fixture_bundle(root)


def test_rejects_missing_passage(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)

    def missing(cases):
        cases[0]["actions"][0]["evidence"][0]["source_id"] = "SYN-A-P9"

    _mutate_cases(root, missing)
    with pytest.raises(FixtureError):
        load_fixture_bundle(root)
