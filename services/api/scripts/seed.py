"""Seed a validated collection into Exasol (repeatable; never wipes or overwrites anything).

    python -m scripts.seed --collection synthetic-demo-v1

The supplied fictional collection is validated first (schema, passage hashes, case ownership,
quote substrings, collection hash/count) by ``app.fixtures``. A second run is a no-op. An existing
collection ID with a different version is refused: publish changed data under a new collection ID.
Real (published) data is a separate collection with reviewed provenance and is not seeded here.
"""
from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.fixtures import FixtureError, load_fixture_bundle
from app.repositories.base import StorageUnavailable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True)
    args = parser.parse_args()
    settings = get_settings()
    try:
        bundle = load_fixture_bundle(settings.fixture_root)
    except FixtureError as exc:
        print(f"seed: FAILED validation - {exc}", file=sys.stderr)
        return 1
    if args.collection != bundle.collection.collection_id:
        print(f"seed: unknown collection {args.collection!r}", file=sys.stderr)
        return 2
    print(f"seed: {bundle.collection.collection_id} validated locally "
          f"({bundle.collection.case_count} fictional cases, mode={bundle.collection.mode}).")

    from app.repositories.exasol import ExasolEncounterRepository

    try:
        repo = ExasolEncounterRepository(
            settings.exasol_dsn, settings.exasol_user, settings.exasol_password, settings.exasol_schema
        )
        if missing := repo.missing_tables():
            print(f"seed: FAILED - run scripts.init_db first (missing {missing})", file=sys.stderr)
            return 1
        outcome = repo.seed_collection(bundle.collection, bundle.cases)
        stored = {c.collection_id: c for c in repo.list_collections()}
        cases = repo.load_cases(bundle.collection.collection_id)
        repo.close()
    except (StorageUnavailable, ValueError) as exc:
        print(f"seed: FAILED - {exc}", file=sys.stderr)
        return 1
    collection = stored.get(bundle.collection.collection_id)
    if collection is None or collection.version != bundle.collection.version or len(cases) != collection.case_count:
        print("seed: FAILED - read-back does not match the validated collection", file=sys.stderr)
        return 1
    passages = sum(len(c.passages) for c in cases)
    print(f"seed: {outcome}; read back {len(cases)} cases and {passages} passages from Exasol "
          f"(version {collection.version[:12]}...).")
    print("seed: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
