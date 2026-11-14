"""Server-owned extraction vocabulary (docs/04-data-and-evidence.md "Patient extraction rules").

This is a small, developer-reviewed alias map for a fictional prototype. It is NOT clinically
validated and adds no outside medical knowledge: an alias maps only words the patient actually
said to the smallest supported value. Anything that no alias covers is either kept raw (for keys
that allow raw values) or rejected. A matching quote is necessary but not proof of meaning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_KEYS = (
    "symptom", "site", "symptom_site", "duration", "prior_treatment_name", "prior_treatment_duration",
    "prior_treatment_response", "exposure", "product_use", "onset", "additional_symptoms",
)
# symptom_site: "<symptom>@<site>", validated by app.extraction.association (not by an alias table).
# product_use: a named product or medication the patient says they used, in their own words. It is
# context only: not the categorical exposure value, not a treatment for this complaint, no purpose,
# dose, timing, cause or response.
MULTI_VALUE_KEYS = frozenset({"symptom", "site", "symptom_site", "product_use", "additional_symptoms"})
NEGATABLE_KEYS = MULTI_VALUE_KEYS
# Keys whose value may be the patient's own words when no alias applies.
RAW_VALUE_KEYS = frozenset({"symptom", "site", "duration", "onset", "additional_symptoms",
                            "prior_treatment_name", "prior_treatment_duration", "product_use"})
# Categorical values used by the structured-v1 exposure conflict gate.
EXPOSURE_GATE_VALUES = frozenset({"new_product", "no_new_product"})

_A = "['\u2019]"  # straight or typographic apostrophe


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_UNIT = {"days": r"\bdays?\b", "weeks": r"\bweeks?\b", "months": r"\bmonths?\b", "years": r"\byears?\b"}
_PRODUCT = r"(?:soaps?|products?|detergents?|lotions?|gloves|cleaners?|shampoos?|washes|wash)"

ALIASES: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "symptom": [
        ("itching", _p(r"\bitch(?:y|ing|es|ed|iness)?\b")),
        ("discomfort", _p(r"\b(?:uncomfortable|discomfort)\b")),
        ("burning", _p(r"\bburn(?:ing|s|ed)?\b")),
        ("pain", _p(r"\b(?:pain|painful)\b")),
        ("dryness", _p(r"\bdry(?:ness)?\b")),
        ("redness", _p(r"\bred(?:ness)?\b")),
        ("rash", _p(r"\brash(?:es)?\b")),
    ],
    "site": [
        # "hand soap" / "hand cream" name a product, not a body site.
        ("hands", _p(r"\bhands?\b(?!\s+(?:soap|cream|wash|lotion|sanitiser|sanitizer|gel)s?\b)")),
        ("scalp", _p(r"\bscalp\b")),
        ("face", _p(r"\bface\b")),
        ("arms", _p(r"\barms?\b")),
        ("legs", _p(r"\blegs?\b")),
        ("feet", _p(r"\b(?:feet|foot)\b")),
        ("wrists", _p(r"\bwrists?\b")),
        ("fingers", _p(r"\bfingers?\b")),
    ],
    "duration": [(value, _p(pattern)) for value, pattern in _UNIT.items()],
    "onset": [],
    "prior_treatment_duration": [
        ("few_days", _p(r"\b(?:a\s+)?(?:few|couple(?:\s+of)?)\s+days\b")),
        *[(value, _p(pattern)) for value, pattern in _UNIT.items()],
    ],
    "prior_treatment_response": [
        ("no_improvement", _p(
            rf"\b(?:did\s*n{_A}?t|did\s+not|does\s*n{_A}?t|does\s+not|was\s*n{_A}?t|was\s+not)\s+(?:really\s+)?"
            rf"(?:help|work|improve|do\s+(?:anything|much))\b|\bno\s+(?:difference|change|improvement)\b|\bdid\s+nothing\b"
        )),
        ("worse", _p(r"\b(?:made\s+it\s+worse|got\s+worse)\b")),
        ("partial_improvement", _p(r"\b(?:helped\s+a\s+(?:bit|little)|a\s+(?:bit|little)\s+better|slightly\s+better)\b")),
        ("improved", _p(r"\b(?:helped|got\s+better|improved|cleared\s+(?:it\s+)?up)\b")),
    ],
    "exposure": [
        ("no_new_product", _p(
            rf"\bno\s+new\s+{_PRODUCT}|\bnothing\s+new\b|\bsame\s+{_PRODUCT}"
            rf"|\b(?:have\s*n{_A}?t|have\s+not|did\s*n{_A}?t|did\s+not)\s+(?:changed?|used|started|switched|tried)\s+"
            rf"(?:any(?:thing)?\s+)?(?:new\s+)?(?:{_PRODUCT}|anything)"
        )),
        ("new_product", _p(
            rf"\b(?:(?:started|began)\s+(?:using\s+|to\s+use\s+)?(?:a\s+)?)?new\s+(?:\w+\s+){{0,2}}?{_PRODUCT}"
            rf"|\b(?:switched|changed)\s+(?:to\s+a\s+new\s+|my\s+|our\s+|the\s+)(?:\w+\s+){{0,2}}?{_PRODUCT}"
        )),
    ],
    "prior_treatment_name": [],
    "product_use": [],
    "additional_symptoms": [],
}

# ------------------------------------------------------------------ product_use
USE_VERB = _p(
    r"\b(?:used|use|uses|using|applied|apply|applies|applying|tried|try|trying|"
    r"started\s+(?:using|on|applying|taking)|start(?:ing)?\s+(?:using|applying|taking)|"
    r"take|takes|taking|took|put\s+on|putting\s+on|rubbed\s+on|rubbing\s+on)\b")
_PRODUCT_STOP = frozenset({
    "for", "around", "on", "at", "when", "since", "before", "after", "and", "but", "or", "because", "to",
    "about", "every", "each", "once", "twice", "daily", "then", "it", "until", "while", "with", "in", "during",
    "last", "that", "which", "who", "so", "if", "as", "from", "of", "a", "lot", "again", "too", "also", "only",
    "just", "really", "still", "now", "here", "there", "already", "recently", "yesterday", "today",
})
_DETERMINERS = frozenset({"a", "an", "the", "some", "my", "this", "any", "her", "his", "our", "their"})
GENERIC_PRODUCT_WORDS = frozenset({
    "cream", "creams", "foam", "soap", "soaps", "shampoo", "shampoos", "wash", "washes", "product", "products",
    "detergent", "detergents", "gloves", "glove", "lotion", "lotions", "ointment", "ointments", "gel", "gels",
    "spray", "sprays", "balm", "moisturiser", "moisturizer", "cleaner", "cleaners", "medicine", "medication",
    "medications", "pills", "pill", "tablets", "tablet", "drops", "new", "hand", "body", "face", "hair", "skin",
    "scalp", "anything", "nothing", "something", "stuff", "different", "other", "same", "much", "more", "them",
    "these", "those", "everything", "every", "all", "usual", "regular", "normal", "one", "kind", "type", "sort",
    "shower", "showers", "bath", "baths", "time", "look", "break", "care", "photo", "photos", "picture",
    "pictures", "place", "part", "walk", "nap", "rest", "while", "long", "day", "days", "week", "weeks", "it",
    "steroid", "steroids", "antibiotic", "antibiotics", "antihistamine", "antihistamines", "pharmacy",
    "drugstore", "bit", "little", "few", "couple", "advice", "notice", "note", "turns",
})
_WORD = re.compile(r"[A-Za-z][\w%'-]*")


def product_mentions(text: str) -> list[tuple[str, int, int, int]]:
    """Named products the patient says they used: (value, verb_start, value_start, value_end).
    The value is up to four of the patient's words after a use verb. It stops at punctuation or
    a function word, and needs at least one word that is not generic ("cream", "new hand soap",
    "something" never count)."""
    out = []
    for verb in USE_VERB.finditer(text):
        words: list[re.Match[str]] = []
        pos = verb.end()
        while len(words) < 4:
            gap = re.match(r"[ \t]+", text[pos:])
            pos += gap.end() if gap else 0
            m = _WORD.match(text, pos)
            if not m:
                break
            word = m.group(0).lower()
            if not words and word in _DETERMINERS:
                pos = m.end()
                continue
            if word in _PRODUCT_STOP:
                break
            words.append(m)
            pos = m.end()
        if words and any(w.group(0).lower() not in GENERIC_PRODUCT_WORDS for w in words):
            out.append((" ".join(w.group(0) for w in words), verb.start(), words[0].start(), words[-1].end()))
    return out


def product_value_supported(quote: str, value: str) -> bool:
    words = [w.lower() for w in _WORD.findall(value)]
    return bool(USE_VERB.search(quote)) and bool(words) and any(w not in GENERIC_PRODUCT_WORDS for w in words)

UNKNOWN_CUE = _p(
    rf"\b(?:do\s*n{_A}?t|do\s+not|can{_A}?t|cannot|not)\s+(?:really\s+)?(?:know|remember|recall|sure)\b"
    rf"|\bno\s+idea\b|\bno\s+clue\b|\bnot\s+a\s+clue\b|\bhave\s*n{_A}?t\s+(?:a\s+clue|any\s+idea)\b"
    r"|\bforg[oe]t\b|\bnot\s+certain\b"
)
NEG_CUE = _p(rf"\b(?:no|not|never|without|none|nothing|neither|nor)\b|n{_A}t\b")
FIELD_CUE: dict[str, re.Pattern[str]] = {
    "prior_treatment_name": _p(r"\b(?:name|called|brand)\b"),
    "prior_treatment_duration": _p(r"\b(?:how\s+long|long|days?|weeks?)\b"),
    "duration": _p(r"\b(?:when|how\s+long|long|began|begin|started|start)\b"),
    "onset": _p(r"\b(?:when|began|begin|started|start)\b"),
    "exposure": _p(r"\b(?:new|changes?|changed|products?|soaps?|different)\b"),
    "site": _p(r"\b(?:where|which\s+part)\b"),
    "symptom": _p(r"\b(?:feels?|what\s+it)\b"),
}
# Whole-turn acknowledgements: never an answer, never a fact.
ACKNOWLEDGEMENT = _p(
    r"^\W*(?:ok(?:ay)?|yes|yeah|yep|sure|thanks?(?:\s+you)?|thank\s+you|hmm+|uh+|um+|right|alright"
    r"|got\s+it|mhm+|cool|i\s+see|hi|hello|hey|good\s+(?:morning|afternoon|evening))"
    r"(?:[\s,.!]+(?:ok(?:ay)?|thanks?|thank\s+you|sure|right|there|hi|hello))*\W*$"
)
# A bare "no" can answer the exposure question; it is interpreted only through that question.
SHORT_NO = _p(r"^\W*(no|nope|nah|not\s+really|nothing(?:\s+new)?|none)\b")
STOP_CUE = _p(rf"\b(?:stop|that{_A}?s\s+all|that\s+is\s+all|no\s+more\s+questions|i{_A}?m\s+done|i\s+am\s+done|let{_A}?s\s+stop)\b")
TREATMENT_FORM = _p(r"\b(?:a|an|some|the|this|that)\s+(cream|ointment|lotion|gel|moisturi[sz]er|spray|balm)\b")
TREATMENT_USE = _p(r"\b(?:used\s+it|using\s+it|applied|put\s+it\s+on|tried\s+it)\b")
# Words that describe a kind of product, never a product name.
GENERIC_TREATMENT_WORDS = frozenset({
    "cream", "ointment", "lotion", "gel", "moisturiser", "moisturizer", "spray", "balm", "medicine",
    "medication", "something", "stuff", "it", "that", "this", "steroid", "steroids", "antibiotic",
    "antihistamine", "pharmacy", "drugstore",
})
_CLAUSE_BREAK = re.compile(r"[.,;:!?]|\bbut\b|\bjust\b|\bonly\b|\band\b", re.IGNORECASE)


@dataclass(frozen=True)
class AliasMatch:
    value: str
    start: int
    end: int


def alias_matches(key: str, text: str) -> list[AliasMatch]:
    """Alias values present in ``text``. A match nested inside another value's match is dropped
    (``no new products`` is not also ``new product``)."""
    found = [
        AliasMatch(value, m.start(), m.end())
        for value, pattern in ALIASES.get(key, [])
        for m in pattern.finditer(text)
    ]
    return [
        a for a in found
        if not any(o is not a and o.value != a.value and o.start <= a.start and a.end <= o.end
                   and (o.end - o.start) > (a.end - a.start) for o in found)
    ]


def canonical(value: str | None) -> str:
    return "" if value is None else re.sub(r"[\s-]+", "_", value.strip().lower())


def negation_start(turn_text: str, start: int) -> int | None:
    """Index of a negation cue shortly before ``start`` in the same clause, else None."""
    window_start = max(0, start - 30)
    window = turn_text[window_start:start]
    last_break = 0
    for m in _CLAUSE_BREAK.finditer(window):
        last_break = m.end()
    cue = None
    for m in NEG_CUE.finditer(window, last_break):
        cue = m
        break
    return window_start + cue.start() if cue else None


def negated_in_context(turn_text: str, start: int) -> bool:
    return negation_start(turn_text, start) is not None


_CLAUSE = re.compile(r"[.;!?,]|\bbut\b|\band\b|\bthough\b", re.IGNORECASE)


def clause_at(text: str, start: int, end: int) -> str:
    """Smallest clause around [start, end): "itchy for weeks, and a cream didn't help" keeps the
    symptom duration and the treatment apart."""
    left = 0
    for m in _CLAUSE.finditer(text, 0, start):
        left = m.end()
    m = _CLAUSE.search(text, end)
    return text[left:m.start() if m else len(text)]


def is_treatment_clause(text: str, start: int, end: int) -> bool:
    clause = clause_at(text, start, end)
    return bool(TREATMENT_USE.search(clause) or TREATMENT_FORM.search(clause))


def clause_end(text: str, start: int) -> int:
    m = re.compile(r"[.;!?,]").search(text, start)
    return m.start() if m else len(text)
