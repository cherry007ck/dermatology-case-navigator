# Ranking `structured-v2`: symptom–site associations

Implemented in `services/api/app/retrieval/structured_v2.py` and `services/api/app/extraction/association.py`. These are prototype engineering rules, not a validated clinical scoring system.

## Why v2 exists

`structured-v1` intersected the patient's sites and symptoms independently. A case with scalp itching and facial swelling therefore qualified for a patient with an itchy face. v2 requires a symptom *at* a shared site.

## Representation

There is no schema change. It uses the existing `PatientFact` and `CaseFeature` shapes with a new key:

- `key = "symptom_site"`
- `value = "<symptom>@<site>"`, using the server vocabulary values, for example `itching@scalp`
- patient fact status is `reported`, `negated` or `conflicting` (never `unknown`); case feature polarity is `affirmed` or `negated`
- evidence is a quote that supports the association itself

The separate `symptom` and `site` facts and features stay as they were.

## When the patient side gets an association

The two rules below are applied by the keyword rules provider, and the server validator enforces them for every provider, including Meta.

1. **Stated together in one clause.**
   - A symptom mention and a site mention link only when the text between them meets all of these:
     - it is at most 40 characters;
     - it contains no punctuation and no "and", "but", "or" or similar break;
     - it contains no other symptom or site mention.
   - Examples: "my scalp itches" links; "itching on my hands" links. "My scalp itches and my face is red" gives two separate links, itching@scalp and redness@face. "Itchy hands and feet" links itching to the hands only.
   - Separate sentences, comma-separated topics ("my scalp, it's just itchy") and bare lists never link.
   - A negation cue before the pair or between its parts makes the association negated ("my hands aren't itchy").
   - "Don't know / not sure" wording in the clause means no association is recorded.
2. **A direct answer to the checklist question.**
   - The answer to "Where on your body is it?" links each reported site in the answer to the single symptom the patient reported elsewhere. The answer to the symptom question works the same way with the single reported site.
   - With several symptoms or sites reported, nothing is linked, because that would be a guess between combinations.
   - The fact cites both quotes.

A Meta candidate `symptom_site` that fails rule 1 against its own quote is rejected with one of these reasons:
- `association_not_stated_together`
- `negation_mismatch`
- `association_uncertain`
- `association_value_format`

## Case side

- **Published records** carry explicit `symptom_site` features with a passage quote. A developer curates them and a human source reviewer checks them. The importer refuses a published record that has no association, or an association whose symptom or site is not also an affirmed feature of the case.
- **Synthetic `synthetic-demo-v1` records** were written before the key existed and are not rewritten, so their collection digest and stored Exasol rows are unchanged. For them, rule 1 is applied to the case's own passages, for the case's own affirmed symptom and site values only. For example, "itching on the hands" gives itching@hands.

## Eligibility and score

1. The source, review and kind gates are unchanged.
2. **Sites:**
   - an explicitly different site gives `site_conflict`;
   - no shared site gives `no_shared_site`.
3. **Symptoms:** no shared symptom gives `no_shared_symptom`.
4. **Exposure:** contradictory explicit exposure gives `exposure_conflict`, as before.
5. **Association gate:**
   - The case is eligible only if a reported patient association equals an affirmed case association.
   - Otherwise it is excluded as `no_shared_symptom`. The stored reason text reads "No symptom is explicitly reported at the same body site in both."
   - If the patient explicitly denies the case's association, the exclusion cites both the denial and the case quote.
6. **Score:** a shared association counts site +3 and symptom +3. Duration +1 and exposure +2 are unchanged. Cards appear in score order, then by `case_id`, at most three.
7. **No-match:** if the patient has no reported association, the reason is `insufficient_information` (or `conflicting_details`), because the basis for comparison is missing. It is not reported as "no comparable cases".

The shared-feature statement is "Shared reported symptom at the same site: itching on the scalp." It cites the patient association quote and the case association quote.

## Stored searches

- Every search records `algorithm_version`.
- Searches stored as `structured-v1` are read exactly as stored and are never recomputed or relabelled.
- The next v2 search for that session gets a new search ID. Its `changes` are attributed to the rule change ("Comparison rules changed to structured-v2 …"), never to new patient details.
- The contract examples in `contracts/examples/` stay as stored `structured-v1` snapshots.

## Known limits

- **Pronouns and topics:** links made only through a pronoun ("they burn") or a comma-separated topic are not recorded. Such patients get separate symptom and site facts. The brief says the site was not clearly linked, and no card appears.
- **Duration:** duration stays generic per case. It cannot be tied to one symptom.
- **Site vocabulary:** sites are not mapped to body regions. "fingers" does not match "hands".
