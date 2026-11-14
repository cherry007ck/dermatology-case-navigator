"""Build pending-review published CaseRecord candidates from original PMC JATS XML.

    python data/tools/build_published_candidates.py

Every passage is an exact, contiguous excerpt of one body paragraph of the original article as
retrieved by ``pmc_fetch.py`` (whitespace normalised as in the JATS text). The script refuses to
write a record if any excerpt is not found verbatim, if a quote is not inside its own passage, or
if the article licence cannot be read from the XML. Output records are always
``source_review.status = "pending"`` and ``clinical_reviewed = false``; a human source reviewer
changes that, never this script.

Features, actions and outcomes are a developer's literal reading of the excerpts, limited to the
server vocabulary values the patient side uses (docs/04-data-and-evidence.md). Anything that is a
translation (e.g. "pruritic" -> itching) is listed in ``review_flags`` for the source reviewer.
Unmentioned information is not recorded; it is never treated as negative.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pmc_fetch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "published" / "candidates"
COLLECTION_ID = "published-derm-v1"
LICENCE_CHECKS = ROOT / "data" / "published" / "licence-checks.json"
RSQ = "\u2019"  # typographic apostrophe used by the source articles

# ---------------------------------------------------------------------------------------------
# Case specifications. Passage = (suffix, body paragraph locator, exact excerpt).
# Feature = (key, value, polarity, passage suffix, exact quote).
# Statement = (text, [(passage suffix, exact quote), ...]).
# ---------------------------------------------------------------------------------------------
SPECS: list[dict] = [
    {
        "pmid": "33173645",
        "pmc_patients_uid": "7647841-1",
        "patient_in_article": "The single patient of this case report (56-year-old man).",
        "passages": [
            ("P1", "body paragraph 2",
             "A 56-year-old man with no relevant past medical history presented to the hospital due to a rash "
             "found in his hands, forearms, and legs. He had been in his usual state of health until a few days "
             "prior to his presentation when he had started developing intensely pruritic vesicular lesions in "
             "the lateral aspect of his bilateral fingers."),
            ("P2", "body paragraph 2",
             "He denied any other symptoms such as fevers, chills, fatigue, rhinorrhea, sore throat, neck pain, "
             "chest pain, shortness of breath, nausea or vomiting, abdominal pain, diarrhea, or urinary discomfort."),
            ("P3", "body paragraph 2",
             "Physical examination showed multiple vesicles and bullae located principally in the palmar aspect "
             "of the right hand with small vesicles in the lateral aspects of the left hand."),
            ("P4", "body paragraph 5",
             "He underwent a laboratory workup including complete blood count, chemistries, and inflammatory "
             "markers including erythrocyte sedimentation rate and C-reactive protein, which were all within "
             "normal limits. Further workup included a potassium hydroxide (KOH) preparation negative for fungal "
             "infection, and negative bacterial and viral cultures. A skin scraping with microscopy was "
             "performed, which was negative for scabies."),
            ("P5", "body paragraph 5",
             f"The patient was treated with local care, which included the use of compresses and soaks with "
             f"Burow{RSQ}s solution. Drainage of the larger vesicles was also performed. Given the extensive "
             f"lesions covering the bilateral hands, forearms, and legs, a short course of prednisone was "
             f"recommended. Pruritus was treated effectively with diphenhydramine."),
            ("P6", "body paragraph 5",
             f"The patient{RSQ}s lesions improved significantly following the treatment."),
        ],
        "features": [
            ("symptom", "rash", "affirmed", "P1", "a rash found in his hands, forearms, and legs"),
            ("symptom", "itching", "affirmed", "P1", "intensely pruritic vesicular lesions"),
            ("site", "hands", "affirmed", "P1", "hands"),
            ("site", "fingers", "affirmed", "P1", "bilateral fingers"),
            ("site", "forearms", "affirmed", "P1", "forearms"),
            ("site", "legs", "affirmed", "P1", "legs"),
            # Symptom–site associations: only where one quote states the symptom at the site.
            ("symptom_site", "rash@hands", "affirmed", "P1", "a rash found in his hands, forearms, and legs"),
            ("symptom_site", "rash@forearms", "affirmed", "P1", "a rash found in his hands, forearms, and legs"),
            ("symptom_site", "rash@legs", "affirmed", "P1", "a rash found in his hands, forearms, and legs"),
            ("symptom_site", "itching@fingers", "affirmed", "P1",
             "intensely pruritic vesicular lesions in the lateral aspect of his bilateral fingers"),
            ("duration", "days", "affirmed", "P1", "a few days prior to his presentation"),
            ("additional_symptoms", "fever", "negated", "P2", "denied any other symptoms such as fevers"),
        ],
        "actions": [
            ("Reported workup: blood tests within normal limits; KOH preparation, bacterial and viral cultures, "
             "and skin scraping for scabies reported negative.",
             [("P4", "which were all within normal limits"),
              ("P4", "potassium hydroxide (KOH) preparation negative for fungal infection"),
              ("P4", "negative bacterial and viral cultures"),
              ("P4", "negative for scabies")]),
            (f"Local care with compresses and soaks with Burow{RSQ}s solution; drainage of the larger vesicles.",
             [("P5", f"compresses and soaks with Burow{RSQ}s solution"),
              ("P5", "Drainage of the larger vesicles was also performed")]),
            ("A short course of prednisone was recommended.",
             [("P5", "a short course of prednisone was recommended")]),
            ("Diphenhydramine was used for pruritus.",
             [("P5", "Pruritus was treated effectively with diphenhydramine")]),
        ],
        "outcomes": [
            ("The authors report pruritus was treated effectively with diphenhydramine.",
             [("P5", "Pruritus was treated effectively with diphenhydramine")]),
            ("The authors report the lesions improved significantly following the treatment "
             "(single case report; no comparison).",
             [("P6", f"The patient{RSQ}s lesions improved significantly following the treatment.")]),
        ],
        "review_flags": [
            "symptom=itching is a translation of the article's 'intensely pruritic'.",
            "duration=days records onset of the presenting complaint 'a few days prior to his presentation' "
            "(the pruritic finger lesions; the forearm/leg rash 'during the same period').",
            "Symptom–site associations (structured-v2 matches on these): rash@hands, rash@forearms and rash@legs "
            "come from the one sentence that lists the three sites for the rash. itching@fingers comes from "
            "'intensely pruritic vesicular lesions ... bilateral fingers'. The article does not state itching of "
            "the hands, forearms or legs, so a patient reporting itchy hands is not matched to this case on itching.",
            "site=forearms is kept raw; the patient vocabulary maps 'arm(s)' to 'arms', not 'forearms'.",
            "Exposure/product history is not mentioned in the article and is therefore not recorded.",
            "The article's clinical diagnosis sentence is intentionally not excerpted; the title names it.",
            "Outcome is the authors' temporal report, not evidence that a specific action caused it.",
        ],
    },
    {
        "pmid": "33564516",
        "pmc_patients_uid": "7861115-1",
        "patient_in_article": "The single patient of this case report (27-year-old woman).",
        "passages": [
            ("P1", "body paragraph 2",
             "This is a case of a 27-year-old woman, not known to have any medical illnesses, who presented to "
             "our dermatology clinic with a painful swelling over the face for two days. Upon further inquiry, "
             "she used topical minoxidil 5% foam for FPHL applied once daily for four days prior to her "
             "presentation. After applying the foam, she reported itchiness over the scalp, and therefore, she "
             "stopped using it. Regardless, the itchiness continued, and she started to develop gradual swelling "
             "over the face."),
            ("P2", "body paragraph 2",
             "She presented to the emergency department one day prior to her appointment in the dermatology "
             "clinic and was given intramuscular diphenhydramine 50mg and oral prednisone 30mg."),
            ("P3", "body paragraph 2",
             "The patient had previously been prescribed minoxidil 5% spray for FPHL, and she reported itchiness "
             "over the scalp. She was then advised to substitute it with minoxidil 5% foam (propylene glycol "
             "free) after which, she presented with her current complaint."),
            ("P4", "body paragraph 2",
             "A patch test was done with a minoxidil solution containing 5% minoxidil in alcohol, and the results "
             "were interpreted by an immunologist, which showed positive sensitization (Figure 1). A patch test "
             "to alcohol and propylene glycol showed no reaction. Consequently, she was advised to avoid topical "
             "minoxidil solution or foam as a treatment for her FPHL."),
        ],
        "features": [
            ("symptom", "itching", "affirmed", "P1", "itchiness over the scalp"),
            ("symptom", "pain", "affirmed", "P1", "painful swelling over the face"),
            ("symptom", "swelling", "affirmed", "P1", "painful swelling over the face"),
            ("site", "scalp", "affirmed", "P1", "scalp"),
            ("site", "face", "affirmed", "P1", "face"),
            # Associations as stated: itching on the scalp; painful swelling on the face. There is
            # deliberately no itching@face, scalp swelling or facial itching.
            ("symptom_site", "itching@scalp", "affirmed", "P1", "itchiness over the scalp"),
            ("symptom_site", "pain@face", "affirmed", "P1", "painful swelling over the face"),
            ("symptom_site", "swelling@face", "affirmed", "P1", "painful swelling over the face"),
            # No generic duration: "for two days" describes the facial swelling only, and a
            # CaseFeature cannot tie a duration to one symptom/site. See review flags.
            ("exposure", "topical_minoxidil_foam", "affirmed", "P1",
             "she used topical minoxidil 5% foam for FPHL applied once daily for four days prior to her presentation"),
        ],
        "actions": [
            ("Earlier, after scalp itchiness with minoxidil 5% spray, she was advised to substitute minoxidil 5% "
             "foam (propylene glycol free).",
             [("P3", "she reported itchiness over the scalp"),
              ("P3", "advised to substitute it with minoxidil 5% foam (propylene glycol free)")]),
            ("The patient stopped using the foam after scalp itchiness.",
             [("P1", "she reported itchiness over the scalp, and therefore, she stopped using it")]),
            ("Emergency department: intramuscular diphenhydramine 50mg and oral prednisone 30mg.",
             [("P2", "was given intramuscular diphenhydramine 50mg and oral prednisone 30mg")]),
            ("Patch testing: minoxidil 5% in alcohol reported as positive sensitization; alcohol and propylene "
             "glycol showed no reaction.",
             [("P4", "which showed positive sensitization"),
              ("P4", "A patch test to alcohol and propylene glycol showed no reaction.")]),
            ("Advised to avoid topical minoxidil solution or foam.",
             [("P4", "she was advised to avoid topical minoxidil solution or foam")]),
        ],
        "outcomes": [
            ("After stopping the foam, the article reports the itchiness continued and facial swelling developed.",
             [("P1", "Regardless, the itchiness continued, and she started to develop gradual swelling over the face.")]),
        ],
        "review_flags": [
            "symptom=itching is a translation of 'itchiness'; symptom=swelling is kept raw.",
            "No duration feature: 'for two days' belongs to the facial swelling, not to the scalp itching. "
            "The current CaseFeature cannot link a duration to one symptom or site, so it is left out of ranking. "
            "The text stays visible in passage P1.",
            "Symptom–site associations (structured-v2 matches on these): itching@scalp, pain@face and "
            "swelling@face. Itching is stated for the scalp only, so a patient reporting an itchy face is not "
            "matched to this case.",
            "exposure=topical_minoxidil_foam is the documented raw exposure, deliberately NOT the 'new_product' "
            "gate value; the article describes a switch from spray to foam.",
            "No outcome after the emergency treatment or the avoidance advice is reported in the case presentation.",
        ],
    },
]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def licence(meta: dict) -> tuple[str, str]:
    """(name, url) of the licence stated in the JATS XML the passages come from. The machine-readable
    ali:license_ref is preferred; it must agree with the <license xlink:href> apart from http/https."""
    ali, href = meta.get("license_ali_ref"), meta.get("license_xlink_href")
    url = ali or href
    if not url or "creativecommons.org/licenses/" not in url:
        raise SystemExit(f"No verifiable Creative Commons licence in the XML ({href!r}, {ali!r}); refusing.")
    if ali and href and ali.split("://", 1)[1] != href.split("://", 1)[1]:
        raise SystemExit(f"XML licence elements disagree ({href!r} vs {ali!r}); refusing.")
    url = "https://" + url.split("://", 1)[1]
    kind, ver = url.rstrip("/").split("/licenses/")[1].split("/")[:2]
    return f"CC {kind.upper()} {ver}", url


def licence_flags(pmcid: str) -> list[str]:
    checks = {c["pmcid"]: c for c in json.loads(LICENCE_CHECKS.read_text(encoding="utf-8"))}
    c = checks.get(pmcid)
    if c is None:
        return ["Licence: publisher PDF not checked (run data/tools/pmc_pdf_licence.py)."]
    s, pdf = c["summary"], c["publisher_pdf"]
    if s["discrepancy"]:
        return [f"Licence version discrepancy (documented, not a blocker): the PMC JATS XML that every passage "
                f"comes from (sha256 {c['xml']['sha256'][:16]}) states {s['xml_licence']}. The publisher PDF "
                f"(sha256 {pdf['sha256'][:16]}, not used for passages) states {s['publisher_pdf_licence']}. The "
                f"record carries the XML licence because the excerpts come from that artifact. Both versions are "
                f"CC BY with the same attribution requirement. Remaining uncertainty: which version the publisher "
                f"intends; this does not change what attribution the card must show."]
    if s["unverified"]:
        return [f"Licence: the PMC JATS XML that every passage comes from states {s['xml_licence']}, which is "
                "sufficient for this record. The publisher PDF could not be fetched without a browser challenge, so "
                "whether it prints a different CC BY version is unknown. No further PDF is required."]
    return [f"Licence: the XML and the publisher PDF both state {s['xml_licence']}."]


def build(spec: dict, retrieved_at: str) -> tuple[dict, dict]:
    info = pmc_fetch.ids(spec["pmid"])
    pmcid = info["pmcid"]
    xml = pmc_fetch.fetch_xml(pmcid)
    meta = pmc_fetch.metadata(xml)
    if meta.get("retracted"):
        raise SystemExit(f"{pmcid} has a retraction notice; refusing.")
    paragraphs = pmc_fetch.paragraphs(xml)
    by_loc = {loc: (sec, txt) for loc, sec, txt in paragraphs}
    case_id = f"PUB-{pmcid}-1"
    lic_name, lic_url = licence(meta)
    sha_bytes = hashlib.sha256(xml.read_bytes()).hexdigest()
    passages, texts = [], {}
    for suffix, loc, excerpt in spec["passages"]:
        section, para = by_loc[loc]
        start = para.find(excerpt)
        if start < 0:
            raise SystemExit(f"{case_id} {suffix}: excerpt is not verbatim in {loc}.")
        # Paragraph number within its section, counting text paragraphs only (not figure captions).
        n = sum(1 for lc, sc, _ in paragraphs[: int(loc.split()[-1])] if sc == section)
        pid = f"{case_id}-{suffix}"
        texts[pid] = excerpt
        passages.append({
            "passage_id": pid, "case_id": case_id, "text": excerpt, "section": section,
            "locator": f"{pmcid} {section}, paragraph {n} ({loc} of the JATS full text), "
                       f"characters {start}-{start + len(excerpt)}",
            "sha256": sha(excerpt),
        })

    def ref(suffix: str, quote: str) -> dict:
        pid = f"{case_id}-{suffix}"
        if quote not in texts[pid]:
            raise SystemExit(f"{case_id}: quote {quote!r} is not inside {pid}.")
        return {"source_type": "case_passage", "source_id": pid, "quote": quote}

    record = {
        "case_id": case_id,
        "collection_id": COLLECTION_ID,
        "source_kind": "published",
        "title": meta["title"],
        "article_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        "article_identifiers": {k: v for k, v in (("pmid", spec["pmid"]), ("pmcid", pmcid), ("doi", info.get("doi")))
                                if v},
        "source_version": f"pmc-efetch-jats sha256:{sha(xml.read_text(encoding='utf-8'))[:16]} retrieved {retrieved_at}",
        "license": f"{lic_name} ({lic_url})",
        "source_review": {"status": "pending", "reviewer": None, "reviewed_at": None},
        "clinical_reviewed": False,
        "passages": passages,
        "features": [{"key": k, "value": v, "polarity": pol, "evidence": [ref(s, q)]}
                     for k, v, pol, s, q in spec["features"]],
        "actions": [{"text": t, "evidence": [ref(s, q) for s, q in refs]} for t, refs in spec["actions"]],
        "outcomes": [{"text": t, "evidence": [ref(s, q) for s, q in refs]} for t, refs in spec["outcomes"]],
        "citation": {"authors": meta["authors"], "journal": meta["journal"], "year": meta["year"],
                     "license_name": lic_name, "license_url": lic_url},
    }
    if not (meta["authors"] and meta["journal"] and meta["year"]):
        raise SystemExit(f"{case_id}: citation metadata missing in the XML; refusing.")
    notes = {
        "case_id": case_id, "pmid": spec["pmid"], "pmcid": pmcid, "doi": info.get("doi"),
        "journal": meta.get("journal"), "year": meta.get("year"), "article_type": meta.get("article_type"),
        "pmc_patients_uid": spec["pmc_patients_uid"], "patient_in_article": spec["patient_in_article"],
        "xml_sha256": sha_bytes, "review_flags": [*licence_flags(pmcid), *spec["review_flags"]],
    }
    return record, notes


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%d")
    notes = []
    for spec in SPECS:
        record, note = build(spec, retrieved_at)
        path = OUT / f"{record['case_id']}.json"
        if path.exists():  # same XML artifact: keep its original retrieval date
            old = json.loads(path.read_text(encoding="utf-8"))
            if old["source_version"].split(" retrieved ")[0] == record["source_version"].split(" retrieved ")[0]:
                record["source_version"] = old["source_version"]
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        notes.append(note)
        print(f"wrote {path.relative_to(ROOT)} ({len(record['passages'])} passages, "
              f"{len(record['features'])} features, review pending)")
    (OUT / "review-notes.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
