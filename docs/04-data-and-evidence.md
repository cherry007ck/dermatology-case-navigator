# Data, evidence and ranking

## Decision clock

Do not hold the UI hostage to literature acquisition. Both lanes start from the supplied fictional fixtures, which exercise the entire contract. Zoro spends **at most 60 minutes of focused work** locating a usable real-source subset; provider downloads can run while other work proceeds. If that fails, remain synthetic-only and say so. Start with 4–8 genuinely reviewed real cases if available, not an unachievable promise to review all 988 candidates. Expand toward 20 only after the end-to-end path works.

PMC-Patients is a published-case-summary dataset, not a ready-made clinician-approved dermatology evidence base. Use the official repository's dataset links. Do not conflate dataset versions or use its citation-derived relevance annotations as medical ground truth. [Official dataset](https://github.com/pmc-patients/pmc-patients)

## Real-source acquisition

1. Obtain the official dataset from its linked distribution, cache it outside git and record version/download URL/checksum. Read the distribution license and per-article reuse terms before bundling text. Avoid blindly loading a huge dataset into RAM; use a streaming parser when needed.
2. Filter likely skin cases by transparent keywords such as skin, dermatitis, pruritus, rash, hand and eczema. These select candidates only; no keyword establishes clinical relevance. Keep case IDs and article identifiers.
3. Retrieve the corresponding article from its original source; manually inspect a few passages. A single source article may describe multiple patients: attach the correct passages to the correct case.
4. For automated full-text reuse, use the currently documented PMC access route with compatible license terms. The legacy PMC OA Web Service is marked unavailable in the current official documentation; do not use an old tutorial that depends on it. [PMC OA status](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/), [current OAI-PMH documentation](https://pmc.ncbi.nlm.nih.gov/tools/oai/).
5. Zoro creates a structured candidate record. Luffy checks the exact passages, attribution and patient association for each case shown in the demo. Record reviewer and timestamp. If neither can verify a statement, remove it or mark it unavailable; do not rely on a model's assertion that a citation supports it.
6. Move only reviewed cases into `data/reviewed/`. Exclude retracted/withdrawn or otherwise questionable sources from the tiny demo set when identified; this is developer screening, not systematic evidence review. Record publication year and source URL.

Do not include copied article text in a public repository without verifying permitted redistribution. Store short permitted passages and attribution, or keep a locally prepared import outside git. Dataset access without a data-use agreement does not remove copyright/license obligations.

## Case record

Required: `case_id`, `collection_id`, `source_kind`, `title`, `article_url`, `article_identifiers`, `source_version`, `license`, `source_review`, `clinical_reviewed`, `passages`, `features`, `actions`, `outcomes`. Use `contracts/domain.schema.json` for the serialized shape.

Each passage has stable ID, exact text, source locator, section and hash (hash filled by importer). Each feature has key/value/polarity and passage refs. Each action/outcome is a short neutral statement plus refs. For real cases, reviewers verify the statement refers to this case and says what the UI claims. Missing outcome stays empty. Do not infer causation from a later improvement.

## Synthetic fallback — strict separation

The supplied fixtures are intentionally fictional software-test narratives. They do not establish a medically meaningful comparison or validate clinical performance. Their occupations/exposures are narrative details for demonstrating filtering, not clinical advice.

- IDs start `SYN-`; collection ID `synthetic-demo-v1`.
- `source_kind=synthetic`, `clinical_reviewed=false`, original article identifiers empty, `article_url=null`, license `team-authored-demo-fixture`.
- Every screen and source drawer says **“Fictional demonstration case — not published evidence.”** Synthetic action/outcome sections say “Fictional recorded action/outcome”; never “reported in the literature.”
- No invented DOI, PMID, PMCID, author, journal, citation link, or claim that a synthetic case came from PMC-Patients.
- Search one collection kind at a time. With no real sources, published mode has no eligible cases and shows the honest no-match message. Synthetic mode may demonstrate ranking mechanics separately.
- If asking an AI to create extra fictional cases, demand the exact schema and these labels, then review for offensive content, unsupported medical advice and fabricated citations. Do not generate clinical recommendations.

## Patient extraction rules

Input: active patient turns only, plus current question metadata for interpreting an answer. Agent turns are context, never evidence. Output candidate facts with exact quotes and turn IDs. Allow keys: `symptom`, `site`, `symptom_site` (added for structured-v2: `"<symptom>@<site>"`, only when stated together; see `docs/data/ranking-structured-v2.md`), `duration`, `prior_treatment_name`, `prior_treatment_duration`, `prior_treatment_response`, `exposure`, `onset`, `additional_symptoms`.

Server validates quote substring in the referenced active patient turn, allowed keys, value mapping, polarity and question context. Use a reviewed alias map for limited normalization (`itchy` -> `itching`, `hands` -> `hands`); preserve raw text alongside it. A real quote alone does not prove the normalized meaning. Reject unsupported mappings such as “cream” -> “steroid,” “weeks” -> “three weeks,” or “didn't help” -> “treatment-resistant.”

Represent unknown, unmentioned, explicitly denied and conflicting separately. Extraction must not add a diagnosis, severity, adherence or treatment correctness. If the provider fails or returns invalid data, retain turns, show an extraction warning, and allow retry/text review. Never use empty facts as a claim that nothing was reported.

MVP briefs are rendered from validated facts and templates; do not generate a second free-form summary with uncited new claims. Preserve exact patient phrases in the evidence drawer. “For the doctor to clarify” is generated from known missing/conflicting fields and explicit comparison differences, not unrestricted medical reasoning.

## Question policy — maximum two questions total

Question 1: if an unnamed prior cream is reported, ask: **“Do you know the cream's name and how long you used it?”** If no such gap exists, choose one unmentioned field from a short neutral prototype checklist, e.g. duration or body location. Do not re-ask a field the patient already explicitly said they do not know. No eligible gap means skip directly to the next step. This checklist is **not clinician-reviewed** until a clinician actually reviews it.

Question 2: only if at least two eligible reviewed cases explicitly contrast on a patient-answerable feature missing in the patient story. For MVP support one difference template, `exposure_context`: **“Before this started, did you notice any change in products, gloves, or activities involving your hands?”** Only offer it for the hands example with supported contrasting exposure passages. In real mode it additionally requires approval of the question's relevance by a clinician; otherwise use only the intake checklist and reserve the difference for the doctor. Synthetic mode demonstrates this rule mechanically and says it is a fictional workflow.

If “I don't know,” record unknown. Skip records skipped. Neither means “no exposure” or “no prior treatment.” Ask no repeated replacement question. Once a patient says they want to stop, proceed to review without further questioning. Do not name candidate diagnoses or treatments to the patient. Cases are doctor-only.

## Deterministic ranking v1

> **Superseded for new searches on 13 Nov 2026 by `structured-v2`** (`docs/data/ranking-structured-v2.md`). v2 requires a symptom stated at a shared site (key `symptom_site`) instead of intersecting sites and symptoms independently. Stored `structured-v1` searches keep their stored result. The rules below describe v1.

Version: `structured-v1`. Values are prototype engineering rules, not a validated clinical scoring system.

1. Exasol selects only source-reviewed cases from the chosen collection/version. Published mode also requires actual article provenance. Synthetic records are never returned in published mode.
2. Case eligibility requires at least one explicitly shared symptom and one explicitly shared site, with evidence for both on each side. Missing either means insufficient information or no comparable cases; no diagnosis-name matching from the patient is needed.
3. An explicitly documented site conflict or directly contradictory explicit exposure value excludes the case. Unmentioned information never creates a contradiction. Limit conflict logic to agreed categorical values; do not invent medical incompatibilities.
4. Score eligible cases: shared site +3; shared symptom +3; explicitly shared duration bucket +1; explicitly shared exposure +2. Prior treatment and case diagnosis are displayed when sourced but do not affect MVP ranking. Do not convert vague “weeks” into a numerical bucket unless the bucket explicitly accepts that exact qualitative value.
5. Return at most three cards, sort by score descending then stable `case_id`. No diagnosis probability or score percentage appears in the UI. Ask the second question only if the actual eligible cases support it.
6. Every search version persists all active input facts, collection hash/version, candidate case versions, score components, exclusions and final order. Rerun uses the same immutable inputs; do not ask the LLM to recreate old rankings. Generate changes from actual old/new sets and ranks. Reasons reference the changed facts and case passages.

The synthetic main story initially retrieves cases A and B with equal symptom/site support; the answer about a new product supplies a value shared with A and explicitly conflicting with B. A remains, B is removed, and the drawer shows why. A third case has a different explicit site and remains excluded. An empty/no-qualifying story produces a brief with no cards. Do not hardcode outcomes based on scenario IDs; tests use ordinary facts and case records.

For these fixtures, allow explicit aliases `itchy -> itching`, `uncomfortable -> discomfort`, `started using a new hand soap -> exposure:new_product`, and an explicit `no new products -> exposure:no_new_product`. The new-product conflict gate applies only to that categorical field, not all possible exposures. Real clinical meaning is not validated by this toy alias map. Synthetic `source_review.status=fixture_checked` means internal quote/ID consistency only; published eligibility requires status `reviewed` and actual original-source review. `source_review_count` in synthetic mode counts fixture consistency checks, with a matching UI label.

## Required validation demonstrations

- Insert an action statement with a missing passage ID: withheld/flagged.
- Insert a genuine quote from the wrong case: withheld/flagged by case ownership validation.
- Insert a quote that exists but does not support a proposed normalized fact: mapping check rejects it or leaves it unverified.
- Real-source semantic support beyond the small alias/template rules is established by review, not a universal “hallucination detector.” Never claim the prototype proves all statements true.
