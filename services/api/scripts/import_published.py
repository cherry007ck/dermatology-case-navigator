"""Import source-reviewed published cases into Exasol as a separate published collection.

    python -m scripts.import_published --collection-id published-derm-v1 --dry-run
    python -m scripts.import_published --collection-id published-derm-v1

Reads only ``data/published/reviewed/PUB-*.json``. Pending candidates live in
``data/published/candidates/`` and are never read here. Every record must carry
``source_review.status = "reviewed"`` with a reviewer and a review time set by a human
(``data/tools/record_source_review.py``); otherwise the whole import is refused.

Idempotent and non-destructive: a second run with the same reviewed set is a no-op; an existing
collection ID with different content is refused (import the changed set under a new ID). The
synthetic collection is never written: the target ID must start with ``published-`` and the
collection mode is always ``published``.
"""
from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.published import PublishedRecordError, build_collection, read_records
from app.repositories.base import StorageUnavailable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--dry-run", action="store_true", help="validate only; do not connect to Exasol")
    args = parser.parse_args()
    settings = get_settings()
    reviewed_dir = settings.fixture_root / "data" / "published" / "reviewed"
    try:
        collection, cases = build_collection(read_records(reviewed_dir), args.collection_id)
    except PublishedRecordError as exc:
        print(f"import_published: REFUSED - {exc}", file=sys.stderr)
        return 1
    print(f"import_published: {collection.collection_id} validated ({collection.case_count} reviewed published "
          f"cases, {sum(len(c.passages) for c in cases)} passages, clinical_reviewed={collection.clinical_reviewed}, "
          f"version {collection.version[:12]}...).")
    for case in cases:
        print(f"  {case.case_id}  {case.article_url}  {case.license}  reviewed by {case.source_review.reviewer}")
    if args.dry_run:
        print("import_published: dry run, nothing written.")
        return 0

    from app.repositories.exasol import ExasolEncounterRepository

    try:
        repo = ExasolEncounterRepository(
            settings.exasol_dsn, settings.exasol_user, settings.exasol_password, settings.exasol_schema
        )
        if missing := repo.missing_tables():
            print(f"import_published: FAILED - run scripts.init_db first (missing {missing})", file=sys.stderr)
            return 1
        before = {c.collection_id: c.version for c in repo.list_collections() if c.collection_id != collection.collection_id}
        outcome = repo.seed_collection(collection, cases)
        after = {c.collection_id: c for c in repo.list_collections()}
        stored = repo.load_cases(collection.collection_id)
        repo.close()
    except (StorageUnavailable, ValueError) as exc:
        print(f"import_published: FAILED - {exc}", file=sys.stderr)
        return 1
    got = after.get(collection.collection_id)
    untouched = all(after.get(cid) and after[cid].version == v for cid, v in before.items())
    if got is None or got.mode != "published" or got.version != collection.version or len(stored) != len(cases) \
            or any(c.source_kind != "published" for c in stored) or not untouched:
        print("import_published: FAILED - read-back does not match, or another collection changed", file=sys.stderr)
        return 1
    print(f"import_published: {outcome}; read back {len(stored)} published cases; "
          f"other collections unchanged: {sorted(before)}.")
    print("import_published: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
