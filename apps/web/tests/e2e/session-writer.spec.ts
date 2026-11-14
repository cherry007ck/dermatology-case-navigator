import { expect, test } from "@playwright/test";

import type { ApiTransport } from "@/lib/api/transport";
import { ApiRequestError } from "@/lib/api/transport";
import type { AppendTurnsRequest, SessionSnapshot, TurnInput } from "@/lib/api/types";
import { SessionWriter } from "@/lib/session/writer";
import { toTurnInput } from "@/lib/voice/sync";
import { normalizeMessage } from "@/lib/voice/transcript";

import created from "../../mocks/fixtures/http/create-session.json";

// Logic-only checks (no browser page): the serialized write queue that carries voice
// transcripts to POST /turns. A fake transport stands in for the API and enforces the
// same revision and duplicate-turn rules as the backend stub.

function fakeApi(opts: { conflictOnce?: boolean; delayMs?: number } = {}) {
  let snap = structuredClone((created as unknown as { snapshot: SessionSnapshot }).snapshot);
  const calls: AppendTurnsRequest[] = [];
  let conflictPending = opts.conflictOnce ?? false;
  const api = {
    mode: "mock",
    getSession: async () => structuredClone(snap),
    appendTurns: async (_id: string, _t: string, body: AppendTurnsRequest) => {
      calls.push(body);
      await new Promise((r) => setTimeout(r, opts.delayMs ?? 0));
      if (conflictPending) {
        conflictPending = false;
        snap = { ...snap, revision: snap.revision + 1 }; // another writer got in first
        throw new ApiRequestError(409, "REVISION_CONFLICT", "Reload the current session.", false);
      }
      if (body.expected_revision !== snap.revision) throw new ApiRequestError(409, "REVISION_CONFLICT", "Reload.", false);
      const known = new Set(snap.turns.map((t) => t.turn_id));
      if (body.turns.some((t) => known.has(t.turn_id))) throw new ApiRequestError(409, "DUPLICATE_TURN_ID", "Exists.", false);
      const turns = body.turns.map((t: TurnInput, i: number) => ({
        ...t, supersedes_turn_id: null, sequence: snap.turns.length + i + 1, created_at: "2026-11-13T12:00:00Z",
      }));
      snap = { ...snap, turns: [...snap.turns, ...turns], revision: snap.revision + (body.turns.some((t) => t.role === "patient") ? 1 : 0) };
      return structuredClone(snap);
    },
  } as unknown as ApiTransport;
  return { api, calls, current: () => snap };
}

let counter = 0;
const rid = () => `req-${++counter}`;

function voiceEvent(eventId: number, role: "user" | "agent", message: string) {
  return normalizeMessage("conv-1", { message, event_id: eventId, role, source: role === "user" ? "user" : "ai" })!;
}

test.describe("session writer (logic)", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop", "logic test runs once");
  });

  test("serializes concurrent voice writes in event order with one revision bump per patient turn", async () => {
    const { api, calls, current } = fakeApi({ delayMs: 20 });
    const writer = new SessionWriter(api, "S-1", "t", rid);
    await writer.refresh();
    const events = [voiceEvent(1, "agent", "Greeting."), voiceEvent(2, "user", "My hands itch."), voiceEvent(3, "user", "For weeks.")];
    await Promise.all(events.map((e) => writer.appendTurns([toTurnInput(e, writer.snapshot)])));
    expect(current().turns.map((t) => t.text)).toEqual(["Greeting.", "My hands itch.", "For weeks."]);
    expect(current().revision).toBe(2); // agent turn does not bump the patient revision
    expect(calls.map((c) => c.expected_revision)).toEqual([0, 0, 1]); // never two writes at one stale revision
    expect(current().turns.every((t) => t.origin === "voice_transcript")).toBe(true);
  });

  test("the same SDK event twice is stored once", async () => {
    const { api, current } = fakeApi();
    const writer = new SessionWriter(api, "S-1", "t", rid);
    const event = voiceEvent(7, "user", "My hands itch.");
    await writer.appendTurns([toTurnInput(event, writer.snapshot)]);
    await writer.appendTurns([toTurnInput(voiceEvent(7, "user", "My hands itch."), writer.snapshot)]);
    expect(current().turns).toHaveLength(1);
    expect(current().turns[0].turn_id).toBe("voice-conv-1-patient-7");
  });

  test("a revision conflict is retried once against the fresh revision without duplicating", async () => {
    const { api, calls, current } = fakeApi({ conflictOnce: true });
    const writer = new SessionWriter(api, "S-1", "t", rid);
    await writer.appendTurns([toTurnInput(voiceEvent(1, "user", "My hands itch."), writer.snapshot)]);
    expect(calls).toHaveLength(2);
    expect(calls[1].expected_revision).toBe(1);
    expect(calls[0].request_id).not.toBe(calls[1].request_id);
    expect(current().turns).toHaveLength(1);
  });

  test("flush waits for every queued write (used before confirmation)", async () => {
    const { api, current } = fakeApi({ delayMs: 30 });
    const writer = new SessionWriter(api, "S-1", "t", rid);
    void writer.appendTurns([toTurnInput(voiceEvent(1, "user", "Late words."), writer.snapshot)]);
    expect(writer.pendingWrites).toBe(1);
    await writer.flush();
    expect(writer.pendingWrites).toBe(0);
    expect(current().turns).toHaveLength(1);
  });

  test("an older polled snapshot never replaces a newer write result", async () => {
    const { api } = fakeApi();
    const writer = new SessionWriter(api, "S-1", "t", rid);
    const stale = await api.getSession("S-1", "t");
    await writer.appendTurns([toTurnInput(voiceEvent(1, "user", "My hands itch."), writer.snapshot)]);
    writer.accept(stale);
    expect(writer.snapshot?.revision).toBe(1);
  });

  test("patient voice turns link to the pending question; agent turns never do", () => {
    const snap = structuredClone((created as unknown as { snapshot: SessionSnapshot }).snapshot);
    snap.state = "awaiting_answer";
    snap.questions = [{
      question_id: "Q1", kind: "intake_gap", template_id: "t", text: "?", status: "asked",
      evidence: [], reason: "", comparison_basis: null, answer_turn_ids: [],
    }];
    expect(toTurnInput(voiceEvent(1, "user", "I don't know."), snap).reply_to_question_id).toBe("Q1");
    expect(toTurnInput(voiceEvent(2, "agent", "Thanks."), snap).reply_to_question_id).toBeNull();
  });
});
