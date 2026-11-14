// Fixture mock transport: replays the shared contract examples (synced from
// contracts/examples by `npm run sync:fixtures`). The UI labels this mode
// "Mock API — shared fixture responses, no backend". It is not extraction,
// ranking or storage; it mirrors the backend S0 stub's replay behaviour.
import { ApiRequestError, type ApiTransport } from "@/lib/api/transport";
import type { AdvanceResult, ApiErrorResponse, ClinicianNote, SessionSnapshot } from "@/lib/api/types";

import afterCream from "./fixtures/after-cream-answer.json";
import afterExposure from "./fixtures/after-exposure-answer.json";
import afterInitial from "./fixtures/after-initial.json";
import noMatch from "./fixtures/no-match.json";
import collections from "./fixtures/http/collections.json";
import createSession from "./fixtures/http/create-session.json";
import conflict from "./fixtures/http/error-revision-conflict.json";
import extractionUnavailable from "./fixtures/http/error-extraction-unavailable.json";
import readiness from "./fixtures/http/readiness.json";

const ADVANCE_EXAMPLES = [afterInitial, afterCream, afterExposure, noMatch] as unknown as AdvanceResult[];
const STORE_KEY = "dcn.mock-sessions";

type Store = Record<string, SessionSnapshot>;

const clone = <T,>(value: T): T => structuredClone(value);
const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

function load(): Store {
  const raw = typeof window !== "undefined" ? sessionStorage.getItem(STORE_KEY) : null;
  return raw ? (JSON.parse(raw) as Store) : {};
}

function save(store: Store): void {
  sessionStorage.setItem(STORE_KEY, JSON.stringify(store));
}

function fail(status: number, body: unknown, requestId?: string): never {
  const typed = clone(body) as ApiErrorResponse;
  throw ApiRequestError.fromBody(status, { ...typed, request_id: requestId ?? typed.request_id });
}

function requireSession(sessionId: string, token: string): SessionSnapshot {
  const snap = load()[sessionId];
  if (!snap || token !== `MOCK-TOKEN-${sessionId}`) {
    throw new ApiRequestError(404, "SESSION_NOT_FOUND", "Session not found or not accessible.", false);
  }
  return snap;
}

function put(snapshot: SessionSnapshot): SessionSnapshot {
  const store = load();
  store[snapshot.session_id] = snapshot;
  save(store);
  return clone(snapshot);
}

// TEST HOOK (mock mode only): sessionStorage "dcn.mock-fail" = {"op","status","code","message","retryable","times"}
// makes the next matching call fail like the real API would (e.g. 503 STORAGE_UNAVAILABLE).
// Lets browser tests exercise retry/error states without a backend. Never active in live mode.
const FAIL_KEY = "dcn.mock-fail";

function maybeFail(op: string, requestId?: string): void {
  const raw = typeof window !== "undefined" ? sessionStorage.getItem(FAIL_KEY) : null;
  if (!raw) return;
  const rule = JSON.parse(raw) as { op: string; status: number; code: string; message: string; retryable: boolean; times?: number };
  if (rule.op !== op) return;
  const times = (rule.times ?? 1) - 1;
  if (times <= 0) sessionStorage.removeItem(FAIL_KEY);
  else sessionStorage.setItem(FAIL_KEY, JSON.stringify({ ...rule, times }));
  throw ApiRequestError.fromBody(rule.status, { error: { code: rule.code, message: rule.message, retryable: rule.retryable }, request_id: requestId ?? null });
}

function requireDemoCode(code: string): void {
  if (!code.trim()) throw new ApiRequestError(403, "BAD_DEMO_CODE", "Demo access code is not valid.", false);
}

const patientTexts = (snap: SessionSnapshot) => snap.turns.filter((t) => t.role === "patient").map((t) => t.text);

export const MOCK_SKIP_WARNING = "Mock skip — the backend skip endpoint is not implemented yet.";
export const MOCK_CORRECTION_WARNING =
  "Mock correction — the backend correction endpoint and recompute are not implemented yet.";

const withWarning = (warnings: string[], warning: string) => (warnings.includes(warning) ? warnings : [...warnings, warning]);

export function createMockTransport(): ApiTransport {
  const delay = () => new Promise((resolve) => setTimeout(resolve, 150));
  return {
    mode: "mock",
    async readiness(code) {
      requireDemoCode(code);
      return clone(readiness) as never;
    },
    async listCollections(code) {
      requireDemoCode(code);
      return clone(collections) as never;
    },
    async createSession(code, body) {
      requireDemoCode(code);
      await delay();
      const sessionId = `MOCK-${body.request_id.slice(0, 8)}`;
      const created = clone(createSession) as unknown as { snapshot: SessionSnapshot };
      const snapshot = put({ ...created.snapshot, session_id: sessionId });
      return { session_id: sessionId, session_token: `MOCK-TOKEN-${sessionId}`, snapshot };
    },
    async getSession(id, token) {
      maybeFail("getSession");
      return clone(requireSession(id, token));
    },
    async appendTurns(id, token, body) {
      maybeFail("appendTurns", body.request_id);
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      if (body.turns.some((t) => snap.turns.some((s) => s.turn_id === t.turn_id))) {
        throw new ApiRequestError(409, "DUPLICATE_TURN_ID", "A turn with this ID already exists.", false);
      }
      await delay();
      for (const t of body.turns) {
        snap.turns.push({ ...t, supersedes_turn_id: null, sequence: snap.turns.length + 1, created_at: now() });
      }
      if (body.turns.some((t) => t.role === "patient")) {
        snap.revision += 1;
        snap.confirmed_revision = null;
        snap.state = "intake";
      }
      return put(snap);
    },
    async advance(id, token, body) {
      maybeFail("advance", body.request_id);
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      await delay();
      const texts = patientTexts(snap);
      const example = ADVANCE_EXAMPLES.find(
        (ex) => ex.snapshot.revision === snap.revision && JSON.stringify(patientTexts(ex.snapshot)) === JSON.stringify(texts),
      );
      if (!example) fail(503, extractionUnavailable, body.request_id);
      const result = clone(example);
      // Clinician notes belong to the session, not to the replayed example.
      result.snapshot = put({ ...result.snapshot, session_id: id, clinician_notes: snap.clinician_notes });
      return result;
    },
    // MOCK-ONLY (S3 UI work): contract-shaped skip until Zoro's service implements it.
    // Records "skipped", never a negative fact; bumps the revision once; old comparisons go stale.
    async skip(id, token, body) {
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      const question = snap.questions.find((q) => q.question_id === body.question_id && q.status === "asked");
      if (!question) throw new ApiRequestError(409, "QUESTION_NOT_PENDING", "That question is no longer waiting for an answer.", false);
      await delay();
      return put({
        ...snap,
        revision: snap.revision + 1,
        state: "intake",
        confirmed_revision: null,
        questions: snap.questions.map((q) => (q.question_id === body.question_id ? { ...q, status: "skipped" } : q)),
        warnings: withWarning(snap.warnings, MOCK_SKIP_WARNING),
      });
    },
    async confirm(id, token, body) {
      maybeFail("confirm", body.request_id);
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      const latest = snap.search_history.at(-1);
      if (snap.state !== "ready_to_confirm" || latest?.patient_revision !== snap.revision || snap.brief?.patient_revision !== snap.revision) {
        throw new ApiRequestError(409, "NOT_READY_TO_CONFIRM", "Review the latest statement before confirming.", false);
      }
      return put({ ...snap, state: "confirmed", confirmed_revision: snap.revision });
    },
    // MOCK-ONLY (S3 UI work): contract-shaped correction until Zoro's service implements it.
    // Appends a "correction" turn that supersedes the original (never overwrites it), bumps the
    // revision once and clears confirmation. Old searches and the brief keep their old
    // patient_revision, so the UI shows them as stale until a real recompute.
    async correct(id, token, body) {
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      const original = snap.turns.find((t) => t.turn_id === body.replaces_turn_id && t.role === "patient");
      const alreadyReplaced = snap.turns.some((t) => t.supersedes_turn_id === body.replaces_turn_id);
      if (!original || alreadyReplaced) {
        throw new ApiRequestError(409, "TURN_NOT_CORRECTABLE", "That statement is not the current version.", false);
      }
      await delay();
      return put({
        ...snap,
        revision: snap.revision + 1,
        state: "intake",
        confirmed_revision: null,
        turns: [
          ...snap.turns,
          {
            turn_id: `MOCK-CORR-${body.request_id.slice(0, 8)}`,
            role: "patient",
            origin: "correction",
            text: body.replacement_text,
            reply_to_question_id: original.reply_to_question_id,
            supersedes_turn_id: original.turn_id,
            sequence: snap.turns.length + 1,
            created_at: now(),
          },
        ],
        warnings: withWarning(snap.warnings, MOCK_CORRECTION_WARNING),
      });
    },
    async addClinicianNote(id, token, body) {
      maybeFail("addClinicianNote", body.request_id);
      const snap = requireSession(id, token);
      if (body.expected_revision !== snap.revision) fail(409, conflict, body.request_id);
      const note: ClinicianNote = {
        note_id: `MOCK-NOTE-${body.request_id.slice(0, 8)}`,
        patient_revision: snap.revision,
        note_text: body.note_text,
        author_label: body.author_label,
        created_at: now(),
      };
      put({ ...snap, clinician_notes: [...snap.clinician_notes, note] });
      return note;
    },
  };
}
