"""Pydantic DTOs must match contracts/domain.schema.json, and every shared example
must parse into the DTOs and serialize back to identical JSON."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import BaseModel

from app import models
from app.config import REPO_ROOT

DOMAIN = json.loads((REPO_ROOT / "contracts/domain.schema.json").read_text(encoding="utf-8"))
DEFS = DOMAIN["$defs"]
EXAMPLES = REPO_ROOT / "contracts/examples"


def _norm(spec: dict):
    """Canonical form of the JSON Schema features the contract relies on."""
    if "$ref" in spec:
        return ("ref", spec["$ref"].rsplit("/", 1)[-1])
    if "anyOf" in spec:
        return ("anyOf", frozenset(_norm(s) for s in spec["anyOf"]))
    kind = spec.get("type")
    if "enum" in spec:
        return ("enum", frozenset(spec["enum"]))
    if "const" in spec:  # Pydantic renders a single-value Literal as const
        return ("enum", frozenset([spec["const"]]))
    if kind == "array":
        return ("array", _norm(spec["items"]))
    if kind == "object":
        extra = spec.get("additionalProperties")
        return ("map", _norm(extra)) if isinstance(extra, dict) else ("object",)
    if kind == "string":
        fmt = spec.get("format") if spec.get("format") == "date-time" else None
        return ("string", fmt, spec.get("minLength"), spec.get("pattern"))
    if kind == "integer":
        return ("integer", spec.get("minimum"))
    return (kind,)


@pytest.mark.parametrize("name", sorted(DEFS))
def test_domain_def_matches_pydantic_model(name: str) -> None:
    model: type[BaseModel] = getattr(models, name)
    generated = model.model_json_schema(ref_template="#/$defs/{model}")
    domain = DEFS[name]
    assert set(generated["properties"]) == set(domain["properties"]), name
    assert set(generated.get("required", [])) == set(domain["required"]), name
    assert generated.get("additionalProperties") is False
    for prop, spec in domain["properties"].items():
        assert _norm(generated["properties"][prop]) == _norm(spec), f"{name}.{prop}"


def _domain_examples() -> list[Path]:
    return sorted(EXAMPLES.glob("*.json"))


def _model_for(value: dict) -> type[BaseModel]:
    if "spoken_message" in value:
        return models.VoiceAdvanceResult
    if "snapshot" in value and "action" in value:
        return models.AdvanceResult
    return models.SessionSnapshot


@pytest.mark.parametrize("path", _domain_examples(), ids=lambda p: p.name)
def test_domain_examples_round_trip(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(DOMAIN).validate(raw)
    parsed = _model_for(raw).model_validate(raw)
    assert parsed.model_dump(mode="json") == raw


HTTP_EXAMPLES = {
    "create-session.json": models.CreateSessionResponse,
    "collections.json": models.CollectionsResponse,
    "readiness.json": models.ReadinessResponse,
    "clinician-note.json": models.ClinicianNote,
    "error-revision-conflict.json": models.ApiErrorResponse,
    "error-extraction-unavailable.json": models.ApiErrorResponse,
}


def test_every_http_example_is_mapped() -> None:
    assert {p.name for p in (EXAMPLES / "http").glob("*.json")} == set(HTTP_EXAMPLES)


@pytest.mark.parametrize("name", sorted(HTTP_EXAMPLES))
def test_http_examples_round_trip(name: str) -> None:
    raw = json.loads((EXAMPLES / "http" / name).read_text(encoding="utf-8"))
    assert HTTP_EXAMPLES[name].model_validate(raw).model_dump(mode="json") == raw


def test_synthetic_cases_parse() -> None:
    for case in json.loads((REPO_ROOT / "data/synthetic/cases.json").read_text(encoding="utf-8")):
        assert models.CaseRecord.model_validate(case).model_dump(mode="json") == case


def test_openapi_has_no_drift() -> None:
    from scripts.export_openapi import TARGET, render

    assert TARGET.read_text(encoding="utf-8").replace("\r\n", "\n") == render(), (
        "Run: python -m scripts.export_openapi"
    )
