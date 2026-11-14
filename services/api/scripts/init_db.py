"""Initialize the Exasol schema (idempotent, never drops or alters existing objects).

    python -m scripts.init_db

Reads EXASOL_DSN / EXASOL_USER / EXASOL_PASSWORD / EXASOL_SCHEMA from the environment or
services/api/.env. Prints table names and counts only; never credentials or connection details.
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.repositories.base import StorageUnavailable


def main() -> int:
    settings = get_settings()
    from app.repositories.exasol import SCHEMA_TABLES, ExasolEncounterRepository

    try:
        repo = ExasolEncounterRepository(
            settings.exasol_dsn, settings.exasol_user, settings.exasol_password, settings.exasol_schema
        )
        created = repo.initialize_schema()
        missing = repo.missing_tables()
        repo.close()
    except StorageUnavailable as exc:
        print(f"init_db: FAILED - {exc}", file=sys.stderr)
        return 1
    print(f"init_db: schema {repo.schema}: created {created or 'nothing (already present)'}")
    if missing:
        print(f"init_db: FAILED - tables still missing: {missing}", file=sys.stderr)
        return 1
    print(f"init_db: PASS - all {len(SCHEMA_TABLES)} tables present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
