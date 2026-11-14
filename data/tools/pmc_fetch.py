"""Retrieve original PMC articles (JATS XML) via NCBI E-utilities, cache them, and report licence metadata.

    python data/tools/pmc_fetch.py <PMID> [<PMID> ...]
    python data/tools/pmc_fetch.py --paragraphs <PMID>       # print numbered body paragraphs with locators

Route: NCBI PMC ID Converter (PMID -> PMCID/DOI) and E-utilities efetch db=pmc (JATS XML). The
licence is read from the article's own <permissions> block; nothing is assumed. XML is cached in
data/raw/pmc/ (gitignored). Requests are rate-limited (< 3/s, no API key).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "pmc"
TOOL = "dermatology-case-navigator-hackathon"
XLINK = "{http://www.w3.org/1999/xlink}href"


def _get(url: str) -> bytes:
    time.sleep(0.4)
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL} (fictional-demo research tool)"})
    return urllib.request.urlopen(req, timeout=60).read()


def ids(pmid: str) -> dict:
    q = urllib.parse.urlencode({"ids": pmid, "format": "json", "tool": TOOL, "email": "noreply@example.invalid"})
    rec = json.loads(_get(f"https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?{q}"))["records"][0]
    return {"pmid": pmid, "pmcid": rec.get("pmcid"), "doi": rec.get("doi")}


def fetch_xml(pmcid: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{pmcid}.xml"
    if not path.exists():
        q = urllib.parse.urlencode({"db": "pmc", "id": pmcid.removeprefix("PMC"), "retmode": "xml", "tool": TOOL})
        path.write_bytes(_get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{q}"))
    return path


def text(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def authors(meta) -> list[str]:
    """Article authors in document order as "Surname Initials" (PubMed style), from
    <contrib contrib-type="author"> only; editors are excluded. Initials come from the given names
    exactly as tagged; nothing is looked up elsewhere."""
    out = []
    for contrib in meta.findall(".//contrib-group/contrib"):
        if contrib.get("contrib-type") != "author":
            continue
        name = contrib.find("name")
        if name is not None:
            surname = text(name.find("surname"))
            given = text(name.find("given-names"))
            initials = "".join(part[0] for part in given.replace("-", " ").replace(".", " ").split() if part)
            out.append(f"{surname} {initials}".strip())
        else:
            label = text(contrib.find("collab")) or text(contrib.find("string-name"))
            if label:
                out.append(label)
    return out


def metadata(path: Path) -> dict:
    root = ET.parse(path).getroot()
    art = root.find(".//article")
    meta = art.find(".//article-meta") if art is not None else None
    if meta is None:
        return {"error": "no article-meta (full text not available via PMC)"}
    lic = meta.find(".//permissions/license")
    ali = next((el for el in meta.iter() if el.tag.endswith("}license_ref")), None)
    pub = next((d for d in meta.findall("pub-date") if d.get("date-type") == "pub"), None)
    if pub is None:
        pub = next((d for d in meta.findall("pub-date") if d.get("pub-type") in ("epub", "ppub")), None)
    year = pub.find("year") if pub is not None else meta.find(".//pub-date/year")
    return {
        "title": text(meta.find(".//article-title")),
        "journal": text(art.find(".//journal-meta//journal-title")),
        "year": year.text if year is not None else None,
        "authors": authors(meta),
        "license_type": lic.get("license-type") if lic is not None else None,
        "license_href": (lic.get(XLINK) if lic is not None else None) or (ali.text if ali is not None else None),
        "license_xlink_href": lic.get(XLINK) if lic is not None else None,
        "license_ali_ref": ali.text.strip() if ali is not None and ali.text else None,
        "license_text": text(lic.find("license-p")) if lic is not None else None,
        "article_type": art.get("article-type"),
        "retracted": any("retract" in (r.get("related-article-type") or "") for r in root.iter("related-article")),
        "body_paragraphs": len(art.findall(".//body//p")),
    }


def paragraphs(path: Path):
    """(locator, section title, paragraph text) for every body paragraph, in document order."""
    root = ET.parse(path).getroot()
    body = root.find(".//article/body")
    out = []

    def walk(el, trail):
        for child in el:
            tag = child.tag
            if tag == "sec":
                title = text(child.find("title"))
                walk(child, trail + [title or "untitled"])
            elif tag == "p":
                out.append((" > ".join(trail) or "body", text(child)))
            elif tag in ("fig", "table-wrap"):
                cap = child.find(".//caption")
                if cap is not None:
                    out.append((" > ".join(trail + [f"{tag} {child.get('id', '')}"]), text(cap)))
    if body is not None:
        walk(body, [])
    return [(f"body paragraph {i + 1}", sec, t) for i, (sec, t) in enumerate(out)]


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--paragraphs":
        info = ids(argv[1])
        for loc, sec, t in paragraphs(fetch_xml(info["pmcid"])):
            print(f"[{loc}] [{sec}]\n{t}\n")
        return 0
    for pmid in argv:
        info = ids(pmid)
        if not info["pmcid"]:
            print(json.dumps({"pmid": pmid, "error": "no PMCID"}))
            continue
        info.update(metadata(fetch_xml(info["pmcid"])))
        print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
