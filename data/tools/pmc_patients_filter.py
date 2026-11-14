"""Find candidate dermatology cases in the official PMC-Patients dataset (Hugging Face CSV).

    python data/tools/pmc_patients_filter.py

Acquisition route: https://huggingface.co/datasets/zhengyun21/PMC-Patients, file PMC-Patients.csv
(dataset licence tag: CC BY-NC-SA 4.0; linked from https://github.com/pmc-patients/pmc-patients).
The file is cached in data/raw/pmc-patients/ (gitignored, never committed) with its SHA-256.

PMC-Patients is used ONLY to discover candidate PMIDs/patients. Quotes and features must come from the
original PMC article, whose own licence governs reuse. Keywords select candidates; they establish
nothing about clinical relevance.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "pmc-patients"
URL = "https://huggingface.co/datasets/zhengyun21/PMC-Patients/resolve/main/PMC-Patients.csv"
TITLE = re.compile(r"\b(dermatitis|eczema|prurit\w*|urticaria|hand|palm\w*|scalp)\b", re.I)
SITE = re.compile(r"\b(hands?|palms?|fingers?|scalp)\b", re.I)
SYMPTOM = re.compile(r"\b(itch\w*|prurit\w*|burning)\b", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "PMC-Patients.csv"
    if not target.exists():
        print("downloading PMC-Patients.csv (~545 MB)")
        urllib.request.urlretrieve(URL, target)
    digest = sha256(target)
    (RAW / "SOURCE.json").write_text(json.dumps({"url": URL, "file": target.name, "sha256": digest,
                                                 "dataset_licence_tag": "cc-by-nc-sa-4.0"}, indent=2), encoding="utf-8")
    csv.field_size_limit(1 << 30)
    n = kept = 0
    with target.open(encoding="utf-8", newline="") as fh, (RAW / "candidates.jsonl").open("w", encoding="utf-8") as out:
        for row in csv.DictReader(fh):
            n += 1
            text, title = row.get("patient") or "", row.get("title") or ""
            if TITLE.search(title) and SITE.search(text) and SYMPTOM.search(text) and len(text) < 3000:
                kept += 1
                out.write(json.dumps({k: row.get(k) for k in ("patient_uid", "PMID", "file_path", "title", "patient")},
                                     ensure_ascii=False) + "\n")
    print(f"sha256 {digest[:16]}...; scanned {n} patient summaries; {kept} keyword candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
