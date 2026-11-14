// One serialized write queue per session (docs/03-api-contract.md: "The browser
// serializes writes per session"). Typed answers and voice transcripts both go
// through it, so writes never race each other on the same expected_revision.
//
// Turn IDs are stable (voice: event-derived; typed: generated once per submit), so a
// retry after a revision conflict can never create a duplicate turn: the backend
// rejects a repeated turn_id, which the writer treats as "already saved".
import { ApiRequestError, type ApiTransport } from "@/lib/api/transport";
import type { AdvanceResult, SessionSnapshot, TurnInput } from "@/lib/api/types";

type Listener = (snapshot: SessionSnapshot) => void;
type PendingListener = (pending: number) => void;

/** Newer-or-equal snapshot wins; a slow poll can never roll back a fresher write result. */
export function isNewer(next: SessionSnapshot, current: SessionSnapshot | null): boolean {
  if (!current) return true;
  if (next.revision !== current.revision) return next.revision > current.revision;
  return (
    next.turns.length >= current.turns.length &&
    next.search_history.length >= current.search_history.length &&
    next.questions.length >= current.questions.length
  );
}

export class SessionWriter {
  private chain: Promise<unknown> = Promise.resolve();
  private pending = 0;
  private current: SessionSnapshot | null = null;
  private readonly listeners = new Set<Listener>();
  private readonly pendingListeners = new Set<PendingListener>();

  constructor(
    private readonly api: ApiTransport,
    private readonly sessionId: string,
    private readonly token: string,
    private readonly newRequestId: () => string,
  ) {}

  get snapshot(): SessionSnapshot | null {
    return this.current;
  }

  get pendingWrites(): number {
    return this.pending;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  subscribePending(listener: PendingListener): () => void {
    this.pendingListeners.add(listener);
    return () => this.pendingListeners.delete(listener);
  }

  /** Apply a snapshot from any source (load, poll, write) if it is not older. */
  accept(snapshot: SessionSnapshot): void {
    if (!isNewer(snapshot, this.current)) return;
    this.current = snapshot;
    this.listeners.forEach((l) => l(snapshot));
  }

  private enqueue<T>(work: () => Promise<T>): Promise<T> {
    this.setPending(this.pending + 1);
    const run = this.chain.then(work, work);
    this.chain = run.catch(() => undefined);
    return run.finally(() => this.setPending(this.pending - 1));
  }

  private setPending(n: number): void {
    this.pending = n;
    this.pendingListeners.forEach((l) => l(n));
  }

  async refresh(): Promise<SessionSnapshot> {
    const snap = await this.api.getSession(this.sessionId, this.token);
    this.accept(snap);
    return this.current ?? snap;
  }

  /**
   * Append turns at the latest known revision. On a revision conflict, re-read and retry
   * once with a fresh request ID. A duplicate-turn rejection means the turn is already
   * stored (e.g. a retried voice event); the writer refreshes and reports success.
   */
  appendTurns(turns: TurnInput[]): Promise<SessionSnapshot> {
    return this.enqueue(async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        const base = this.current ?? (await this.refresh());
        const already = new Set(base.turns.map((t) => t.turn_id));
        const fresh = turns.filter((t) => !already.has(t.turn_id));
        if (fresh.length === 0) return base; // deduplicated locally
        try {
          const snap = await this.api.appendTurns(this.sessionId, this.token, {
            request_id: this.newRequestId(),
            expected_revision: base.revision,
            turns: fresh,
          });
          this.accept(snap);
          return snap;
        } catch (e) {
          if (e instanceof ApiRequestError && e.code === "DUPLICATE_TURN_ID") return this.refresh();
          if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT" && attempt === 0) {
            await this.refresh();
            continue;
          }
          throw e;
        }
      }
      throw new ApiRequestError(409, "REVISION_CONFLICT", "Reload the current session.", false);
    });
  }

  /** Browser-initiated advance (typed flow). Voice advances come from the agent's webhook instead. */
  advance(): Promise<AdvanceResult> {
    return this.enqueue(async () => {
      const base = this.current ?? (await this.refresh());
      const result = await this.api.advance(this.sessionId, this.token, {
        request_id: this.newRequestId(),
        expected_revision: base.revision,
      });
      this.accept(result.snapshot);
      return result;
    });
  }

  /** Any other revision-checked write (skip, confirm, ...), serialized with the rest. */
  write(work: (snapshot: SessionSnapshot) => Promise<SessionSnapshot>): Promise<SessionSnapshot> {
    return this.enqueue(async () => {
      const base = this.current ?? (await this.refresh());
      const snap = await work(base);
      this.accept(snap);
      return snap;
    });
  }

  /** Resolves once every queued write has settled (used before review/confirmation). */
  async flush(): Promise<void> {
    await this.chain;
  }
}
