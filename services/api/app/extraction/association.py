"""Symptom–site associations (fact/feature key ``symptom_site``, value ``"<symptom>@<site>"``).

A separate symptom and a separate site in the same turn, paragraph or list are NOT an association.
On the patient side an association is supported only by text that states the symptom at the site:

1. Within one clause. A symptom mention and a site mention (server alias values) count as linked
   only if the text between them is short, contains no clause or list break (punctuation, "and",
   "but", "or", ...) and contains no other symptom or site mention. "My scalp itches" and
   "itching on my hands" link. "My scalp itches and my face is swollen" does not link itching to
   the face, and "itchy hands and feet" links itching to the hands only.
2. By a direct answer. The answer to the "Where on your body is it?" question names the site of
   the single symptom the patient reported (and the answer to "How would you describe what you
   feel there?" names the symptom at the single site reported). With several symptoms or sites
   reported, no association is drawn: that would be a guess between combinations.

A negation cue in the clause before the pair, or between its parts, makes the association
negated ("my hands aren't itchy"). "Don't know / not sure" wording in the clause means no
association is recorded. Every association still passes ``app.evidence.validate`` against the
patient's exact words, whichever provider proposed it.

Case-side associations are explicit case features with a case-passage quote. Published records
carry curated features that a human source reviewer checks. Synthetic fixture records written
before this key existed get theirs from rule 1 applied to their own passages (see
``app.retrieval.structured_v2``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.extraction.vocabulary import NEG_CUE, UNKNOWN_CUE, alias_matches, canonical, clause_at, negation_start

KEY = "symptom_site"
SEP = "@"
MAX_GAP = 40
_BREAK = re.compile(
    r"[.;:!?,()\[\]\n]|\b(?:and|but|or|nor|though|although|while|whereas|plus|also|then|except|besides|unlike)\b",
    re.IGNORECASE)


def join(symptom: str, site: str) -> str:
    return f"{canonical(symptom)}{SEP}{canonical(site)}"


def split(value: str | None) -> tuple[str, str] | None:
    parts = (value or "").split(SEP)
    if len(parts) != 2 or not all(p.strip() for p in parts):
        return None
    return canonical(parts[0]), canonical(parts[1])


def human(value: str) -> str:
    pair = split(value)
    if pair is None:
        return value.replace("_", " ")
    return f"{pair[0].replace('_', ' ')} on the {pair[1].replace('_', ' ')}"


@dataclass(frozen=True)
class _Mention:
    kind: str  # symptom | site
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class Link:
    symptom: str
    site: str
    start: int  # quote start (includes a leading negation cue)
    end: int
    pair_start: int
    negated: bool
    uncertain: bool

    @property
    def value(self) -> str:
        return join(self.symptom, self.site)


def _mentions(text: str) -> list[_Mention]:
    return [_Mention(kind, m.value, m.start, m.end) for kind in ("symptom", "site") for m in alias_matches(kind, text)]


def links(text: str) -> list[Link]:
    """Every clause-level symptom–site link in ``text`` (rule 1), in text order."""
    mentions = _mentions(text)
    out: list[Link] = []
    for s in (m for m in mentions if m.kind == "symptom"):
        for site in (m for m in mentions if m.kind == "site"):
            a, b = (s, site) if s.start < site.start else (site, s)
            if a.end > b.start:
                continue
            gap = text[a.end:b.start]
            if len(gap) > MAX_GAP or _BREAK.search(gap):
                continue
            if any(m is not s and m is not site and a.end <= m.start and m.end <= b.start for m in mentions):
                continue
            cue = negation_start(text, a.start)
            inner = NEG_CUE.search(gap)
            negated = cue is not None or inner is not None
            start = cue if cue is not None else a.start
            uncertain = bool(UNKNOWN_CUE.search(clause_at(text, a.start, b.end)))
            out.append(Link(s.value, site.value, start, b.end, a.start, negated, uncertain))
    return sorted(out, key=lambda link: (link.start, link.end, link.value))


def supported(text: str, quote_start: int, quote_end: int, value: str, negated: bool) -> str | None:
    """None if ``value`` is a rule-1 link fully inside the quote with the given polarity; else the
    rejection reason."""
    pair = split(value)
    if pair is None:
        return "association_value_format"
    found = [lk for lk in links(text) if (lk.symptom, lk.site) == pair
             and quote_start <= lk.pair_start and lk.end <= quote_end]
    if not found:
        return "association_not_stated_together"
    if all(lk.uncertain for lk in found):
        return "association_uncertain"
    if not any(lk.negated == negated and not lk.uncertain for lk in found):
        return "negation_mismatch"
    if negated and not any(quote_start <= lk.start for lk in found if lk.negated):
        return "negation_mismatch"  # the quote must include the negating words
    return None
