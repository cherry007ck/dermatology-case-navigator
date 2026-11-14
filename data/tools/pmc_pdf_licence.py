"""Record the licence of each source artifact: the PMC JATS XML used for every passage, and the
publisher PDF where it can be retrieved without a browser challenge.

    python data/tools/pmc_pdf_licence.py        # writes data/published/licence-checks.json

Passages are taken from the PMC JATS XML only, so the XML licence is the one the records carry.
The publisher PDF is checked to surface version discrepancies for the human reviewer. Download
pages that answer with a JavaScript/bot challenge are reported as "not retrieved" and are never
bypassed. Artifacts are cached in data/raw/ (gitignored); only hashes and licence text are kept.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pmc_fetch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "pmc-pdf"
OUT = ROOT / "data" / "published" / "licence-checks.json"
UA = {"User-Agent": "Mozilla/5.0 (dermatology-case-navigator hackathon licence check)"}

# Publisher PDF locations found for each article (None: no directly retrievable PDF found).
PUBLISHER_PDF: dict[str, str | None] = {
    "PMC7647841": None,
    "PMC7861115": "https://assets.cureus.com/uploads/case_report/pdf/48654/1612453376-20210204-15914-p855nr.pdf",
}
ATTEMPTS_WITHOUT_PDF = {
    "PMC7647841": [
        "PMC article PDF link returned an HTML 'Preparing to download' interstitial, not a PDF.",
        "Europe PMC PDF render returned a browser challenge page.",
        "Cureus article page (self-uri in the XML) returned HTTP 403 to a scripted request.",
    ],
}


def _get(url: str) -> bytes:
    time.sleep(0.4)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def pdf_statements(data: bytes) -> list[str]:
    from pypdf import PdfReader

    text = " ".join(" ".join((pg.extract_text() or "").split()) for pg in PdfReader(io.BytesIO(data)).pages)
    return sorted({" ".join(m.group(0).split()) for m in re.finditer(
        r"This is an open access article.{0,300}?credited\.", text)})


def check(pmcid: str) -> dict:
    xml = pmc_fetch.fetch_xml(pmcid)
    meta = pmc_fetch.metadata(xml)
    entry = {
        "pmcid": pmcid,
        "xml": {
            "artifact": f"NCBI E-utilities efetch db=pmc id={pmcid.removeprefix('PMC')} (JATS XML)",
            "sha256": hashlib.sha256(xml.read_bytes()).hexdigest(),
            "license_xlink_href": meta["license_xlink_href"],
            "license_ali_ref": meta["license_ali_ref"],
            "license_text": meta["license_text"],
            "used_for_passages": True,
        },
    }
    url = PUBLISHER_PDF.get(pmcid)
    if not url:
        entry["publisher_pdf"] = {"status": "not_retrieved", "attempts": ATTEMPTS_WITHOUT_PDF.get(pmcid, [])}
        return entry
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{pmcid}.publisher.pdf"
    try:
        if not path.exists():
            path.write_bytes(_get(url))
        data = path.read_bytes()
        if not data.startswith(b"%PDF-"):
            path.unlink()
            raise ValueError("response is not a PDF")
        entry["publisher_pdf"] = {"status": "retrieved", "url": url,
                                  "sha256": hashlib.sha256(data).hexdigest(),
                                  "licence_statements": pdf_statements(data), "used_for_passages": False}
    except (urllib.error.URLError, ValueError) as exc:
        entry["publisher_pdf"] = {"status": "not_retrieved", "url": url, "attempts": [type(exc).__name__]}
    return entry


def version(href: str | None) -> str | None:
    m = re.search(r"licenses/([a-z-]+)/(\d\.\d)", href or "")
    return f"CC {m.group(1).upper()} {m.group(2)}" if m else None


def main() -> int:
    results = []
    for pmcid in PUBLISHER_PDF:
        entry = check(pmcid)
        xml_v = version(entry["xml"]["license_ali_ref"] or entry["xml"]["license_xlink_href"])
        pdf = entry["publisher_pdf"]
        pdf_v = None
        for s in pdf.get("licence_statements", []):
            m = re.search(r"CC-BY (\d\.\d)", s)
            pdf_v = f"CC BY {m.group(1)}" if m else pdf_v
        entry["summary"] = {
            "xml_licence": xml_v, "publisher_pdf_licence": pdf_v,
            "discrepancy": bool(pdf_v and xml_v and pdf_v != xml_v),
            "unverified": pdf["status"] != "retrieved",
        }
        results.append(entry)
        print(json.dumps({"pmcid": pmcid, **entry["summary"]}))
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
