# Frozen v1 integration contract

Owner after S0: Zoro. Consumer: Luffy. Agree changes together before implementation. `contracts/domain.schema.json` defines domain objects; Zoro implements matching Pydantic DTOs, exports the full endpoint OpenAPI document to `contracts/openapi.json`, and Luffy generates TypeScript types into `apps/web/lib/api/generated.ts`. The exported schema is checked for drift in CI. This pack supplies a domain contract and fixtures, not a completed FastAPI implementation.

## Conventions

Base path `/v1`. JSON uses snake_case. IDs are opaque strings; timestamps are ISO-8601 UTC. A `revision` is the **patient-content revision**, starting at 0. Appending patient content, correcting content or skipping a question increments it once per successful operation. Agent-only transcript batches, search computation, confirmation and clinician notes do not increment patient revision. Every operation that uses a revision rejects stale input with 409 and makes no changes.

Every mutating request has `request_id` (client UUID) and, for an existing session, `expected_revision`. Reusing the same request ID with identical content returns its original response; with different content returns 409. Input hash includes route and session. The browser serializes writes per session. Webhook advances use a server-derived operation key from binding + latest unconsumed patient-turn ID; they cannot issue a second question for the same answer.

All normal session routes require `Authorization: Bearer <session_token>`. Create session requires `X-Demo-Access-Code`; rate-limit it and cap session/utterance sizes. This is fictional-demo access, not a clinician identity system. Token must be cryptographically unpredictable, stored hashed by backend, returned only at session creation and held in browser sessionStorage. To support a retried creation without persisting the raw token, derive it with HMAC-SHA256 using `SESSION_TOKEN_SECRET` over a domain-separated string containing the random session ID and original creation request ID; reconstruct only after the same authenticated creation request. Store the request-to-session mapping, not the raw bearer. Use a standard crypto library and constant-time comparisons. Doctor navigation uses the same tab/sessionStorage token, never token-bearing URLs. A new device/tab must create a new demo encounter unless an explicit sharing flow is added later.

API errors: `{ "error": { "code": "REVISION_CONFLICT", "message": "Reload the current session.", "retryable": false }, "request_id": "..." }`. Use 401 missing/invalid auth, 403 bad demo code, 404 inaccessible/missing resource, 409 stale revision/idempotency mismatch, 422 invalid data, 429 rate limit, 503 provider/storage unavailable. Do not include credentials, raw SQL or provider request bodies in errors.

## Routes

| Method and route | Request | Response |
|---|---|---|
| `GET /health` | None | `{status: "ok"}`; liveness only, no secrets |
| `GET /v1/readiness` | Demo access code | `{storage, extractor, collection_mode, loaded_cases, ready}`; explicit actual modes |
| `POST /v1/sessions` | `{request_id, collection_id}` + demo code | `{session_id, session_token, snapshot}` |
| `GET /v1/collections` | Demo access code | Available collection ID/mode/version/review count; no session data |
| `GET /v1/sessions/{id}` | Bearer token | `SessionSnapshot` |
| `POST /v1/sessions/{id}/turns` | `{request_id, expected_revision, turns: [TurnInput]}` | `SessionSnapshot` |
| `POST /v1/sessions/{id}/advance` | `{request_id, expected_revision}` | `AdvanceResult` |
| `POST /v1/sessions/{id}/skip` | `{request_id, expected_revision, question_id}` | `SessionSnapshot`; records skipped, not a negative fact |
| `POST /v1/sessions/{id}/confirm` | `{request_id, expected_revision}` | `SessionSnapshot`; require processed search at this revision |
| `POST /v1/sessions/{id}/corrections` | `{request_id, expected_revision, replaces_turn_id, replacement_text}` | `SessionSnapshot`; new correction turn; no destructive overwrite |
| `POST /v1/sessions/{id}/clinician-notes` | `{request_id, expected_revision, note_text, author_label}` | `{note_id, patient_revision, note_text, author_label, created_at}` |
| `POST /v1/sessions/{id}/voice-binding` | `{request_id, expected_revision}` + bearer | `{binding_token, expires_at}`; Luffy's module |
| `POST /v1/voice/advance` | Empty object; headers below | Voice-safe `VoiceAdvanceResult`; Luffy's module |
| `POST /api/voice-session` (Next.js server route) | `{session_id, expected_revision, request_id}` + bearer | `{signed_url, binding_token, expires_at}` |

No standalone public article endpoint is required; authorized session snapshots embed the small set of reviewed passages used by cards. Immutable evidence IDs resolve to these passages in the source drawer. Do not include tokens in snapshot JSON.

## Shared shapes

Canonical details are in the machine schema. Important fields:

```typescript
type SessionState = "intake" | "awaiting_answer" | "ready_to_confirm" | "confirmed";
type SourceKind = "published" | "synthetic";
type EvidenceRef = {
  source_type: "patient_turn" | "case_passage";
  source_id: string;
  quote: string; // exact substring; no fabricated offsets
};
type TurnInput = {
  turn_id: string; role: "patient" | "agent";
  origin: "typed" | "voice_transcript";
  text: string; reply_to_question_id: string | null;
};
type PatientFact = {
  fact_id: string; key: string; value: string | null;
  status: "reported" | "negated" | "unknown" | "conflicting";
  evidence: EvidenceRef[];
};
type AdvanceResult = {
  snapshot: SessionSnapshot;
  action: "ask" | "ready_to_confirm" | "waiting_for_transcript";
  question: Question | null;
};
```

`SessionSnapshot` contains `session_id`, `revision`, `state`, `confirmed_revision`, `turns`, `facts`, `questions`, `search_history`, `brief`, `clinician_notes`, `warnings`, `modes` and `collection`. Each search contains its own `patient_revision`; UI must not render it as current unless that equals the snapshot's revision. `brief` is null before extraction. Pending provider work may return a useful technical error, not a success-shaped empty brief.

`modes` is `{storage: "memory" | "exasol", extractor: "fixture" | "gemini"}`. `collection` is `{collection_id, mode, version, case_count, source_review_count, clinical_reviewed}`. `clinical_reviewed` is false unless supported by an actual reviewer record. No user-visible 988 count is hardcoded.

`Question` includes stable `question_id`, `kind` (`intake_gap` or `case_difference`), `template_id`, `text`, `status`, `evidence`, `reason`, `answer_turn_ids`. A case-difference question also includes two case IDs and supported contrasting features in its reason metadata. It never contains a diagnosis or treatment suggestion in the patient-facing `text`.

`CaseCard` includes `case_id`, `source_kind`, `title`, nullable `article_url`, `shared_features`, `important_differences`, `actions`, `outcomes`, and `passages`. Each feature/action/outcome is `{text, evidence: EvidenceRef[]}`. Published cards have an original source link and developer-reviewed passage references; synthetic cards have no external article link. If an outcome is absent, return an empty list and the UI says “Outcome not reported in the reviewed passages.”

`SearchVersion` includes immutable `search_id`, `patient_revision`, `algorithm_version`, `collection_version`, `input_fact_ids`, `ranked_case_ids`, `cards`, `excluded_cases`, `changes`, `no_match_reason`, `created_at`. `changes` is a list of `{case_id, change: appeared|removed|moved|unchanged, from_rank, to_rank, reason, evidence}`. Ranks are 1-based or null. `no_match_reason` is null or `insufficient_information|conflicting_details|no_comparable_cases`. Excluded cases carry deterministic gate reasons, not an LLM opinion.

`Brief` includes `patient_revision`, `summary_items`, `timeline_items`, `prior_treatment_items`, `unresolved_items`, `doctor_clarifications`. Patient-derived items include exact `EvidenceRef`s. Unknowns may have no evidence if explicitly marked as missing, e.g. “Cream name not provided.” Doctor clarifications have `basis_fact_ids` and optional `basis_case_ids`; no unsupported assertions.

## Stable service seam — created in S0

`IntakeService` is obtained through FastAPI dependency injection in both route modules. Freeze these method names and their DTO arguments in `services/api/app/intake_service.py`:

```text
create_session(CreateSessionRequest) -> CreateSessionResponse
get_session(session_id, session_token) -> SessionSnapshot
append_turns(session_id, session_token, AppendTurnsRequest) -> SessionSnapshot
advance(session_id, AdvanceRequest) -> AdvanceResult
skip_question(session_id, session_token, SkipQuestionRequest) -> SessionSnapshot
correct_turn(session_id, session_token, CorrectionRequest) -> SessionSnapshot
confirm(session_id, session_token, ConfirmRequest) -> SessionSnapshot
add_clinician_note(session_id, session_token, ClinicianNoteRequest) -> ClinicianNote
```

The normal `advance` route authenticates its session before calling `advance`; the voice module authenticates its binding before calling it. Never expose `advance` directly without one of these checks. Shared DTOs live in `app/models.py` (Zoro); Luffy imports them and changes only `app/voice`. S0 stubs return validated synthetic fixtures and are visibly marked as stubs; S1 replaces them incrementally.

## Text sequence

1. Enter demo code; select a published or synthetic collection. Create session.
2. Append initial patient statement. Backend stores exact text, increments revision, invalidates confirmation and marks old search stale.
3. Advance at the returned revision. Extract/validate facts, search, save search snapshot. Offer intake-gap question if eligible.
4. Append the answer with `reply_to_question_id`. Advance again. Resolve unknown/skip faithfully, rerank, then offer one supported case-difference question if eligible. Otherwise become ready to confirm.
5. Repeat for the second answer, or call skip. Each question may be offered only once. No more than two questions total; no repeated attempts to get an answer the patient cannot give.
6. Show editable final patient turns and brief. Confirm only after patient review. Doctor workspace requires `state=confirmed` and `confirmed_revision=revision`.

Correction endpoint appends a turn with a `supersedes_turn_id` reference. Keep original text in history; extraction uses only active patient turns. Correction clears `confirmed_revision`, brief/current search validity and relevant answer links; recompute before reconfirming. It does not reset the two-question budget or endlessly restart the interview.

## Voice sequence and authentication — Luffy owns this adapter

1. Use the same session as text intake. Browser calls Next.js `POST /api/voice-session` with its session bearer token. Server verifies it via backend, gets a scoped voice binding, then requests the signed URL from ElevenLabs with its server-only API key. Return signed URL and binding token; never log them. Same-origin checks, rate limit and body limits protect this route too.
2. Start the React SDK session with that signed URL and the connection mode required by the installed SDK (explicit WebSocket for signed WebSocket URLs). Provide non-LLM dynamic variable `voice_binding` containing the binding token. Enable user transcript events in agent configuration.
3. Configure a **server/webhook tool** `advance_intake` to POST `{}` to `https://BACKEND/v1/voice/advance`, with static secret header `X-Tool-Secret` from the agent's secret store and dynamic header `X-Voice-Binding: {{voice_binding}}`. Bindings are random, scoped to one session, expire after 30 minutes, and are revocable. The model is not asked to generate session IDs, credentials, patient facts or quotes. Verify dashboard dynamic-variable syntax against current docs.
4. Browser's SDK adapter forwards **finalized** user/agent transcript events through `/turns` in order, with stable event-derived turn IDs or a deduplicated sequence. Partial ASR events must never append duplicate facts. Do not label ASR output as a verbatim recording; show “Voice transcript — please review.” Only patient-role active turns can support patient facts.
5. When the user finishes a statement/answer, agent calls `advance_intake`. The webhook checks both headers, resolves its own session ID from the binding, waits at most 2 seconds for a newly persisted patient turn if needed, and invokes the shared service using that turn/revision. Never accept a model-supplied transcript as the authoritative source.
6. Return only `{action, question_id, question_text, spoken_message}` to ElevenLabs. Do not return cases, diagnoses, actions/outcomes or clinician content. For `ask`, speak the approved question exactly. For `ready_to_confirm`, ask the user to review and confirm in the web app; do not confirm for them. For `waiting_for_transcript`, one bounded retry is allowed; after that use a technical message and text fallback. Duplicate calls return the previous applicable question/result.
7. Browser polls authenticated snapshot every 500–1000 ms during an active encounter to update issued questions/brief. Stop polling when inactive; serialize writes. A user voice answer is linked to the pending issued question; if the browser did not yet receive its ID, backend can link a later patient turn to the pending question based on stored sequence, never an earlier turn. Test this race explicitly.
8. Before confirmation stop voice capture, await the transcript-write queue, recompute latest revision, show the final review, and then enable Confirm. A late transcript invalidates confirmation and requires another review; it must not silently update an already approved brief.

If transcript delivery or dynamic-header configuration cannot be verified within the voice timebox, ship typed intake plus optional narration as a clearly labelled fallback. Do not pass fabricated patient quotes from agent-generated JSON just to make the demo work. A local backend needs a reachable HTTPS tunnel for a webhook; if no tunnel is available, use the deployed stub/backend early. Never expose an unauthenticated local admin route through a tunnel.

Voice bindings may be in-memory for the single-process prototype; a restart invalidates them and requires reconnecting. Encounter state, search history and patient-token hashes remain in Exasol in live mode. A 401 binding failure is a reconnect state, not data loss.
