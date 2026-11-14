"""Record a HUMAN source review of one published candidate (run by the reviewer, never by an agent).

    python data/tools/record_source_review.py PUB-PMC7647841-1 --reviewer "Full Name" --i-checked-the-article

Copies ``data/published/candidates/<case>.json`` to ``data/published/reviewed/<case>.json`` with
``source_review = {status: reviewed, reviewer, reviewed_at: now}``. Nothing else changes; in
particular ``clinical_reviewed`` stays as it is (false), because source review is not clinical
review. Before running, the reviewer opens the article link and confirms each passage, quote,
locator, licence and the correct patient (see docs/data/published-review.md). If anything needs
correcting, fix the spec in build_published_candidates.py, rebuild, then review again.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "published"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--i-checked-the-article", action="store_true", required=True)
    args = parser.parse_args()
    if len(args.reviewer.strip()) < 2:
        print("A reviewer name is required.", file=sys.stderr)
        return 2
    src = BASE / "candidates" / f"{args.case_id}.json"
    record = json.loads(src.read_text(encoding="utf-8"))
    record["source_review"] = {
        "status": "reviewed", "reviewer": args.reviewer.strip(),
        "reviewed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    out = BASE / "reviewed" / src.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded source review of {args.case_id} by {record['source_review']['reviewer']} -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
