"""Export the FastAPI OpenAPI document to contracts/openapi.json.

    python -m scripts.export_openapi          # write
    python -m scripts.export_openapi --check  # exit 1 if the checked-in file has drifted (CI)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("APP_ENV", "test")

from app.config import REPO_ROOT  # noqa: E402
from app.main import create_app  # noqa: E402

TARGET = REPO_ROOT / "contracts" / "openapi.json"


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = render()
    if args.check:
        existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if existing.replace("\r\n", "\n") != current:
            print("contracts/openapi.json is out of date. Run: python -m scripts.export_openapi", file=sys.stderr)
            return 1
        print("contracts/openapi.json matches the FastAPI app.")
        return 0
    TARGET.write_text(current, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
