import "server-only";

// Fixed-window limiter, per server instance. On Vercel each instance keeps its own
// counters, so this is best-effort abuse damping for a fictional demo, not a quota system.
const WINDOW_MS = 60_000;
const buckets = new Map<string, { start: number; count: number }>();

export function allowRequest(key: string, limit: number, now = Date.now()): boolean {
  const bucket = buckets.get(key);
  if (!bucket || now - bucket.start >= WINDOW_MS) {
    buckets.set(key, { start: now, count: 1 });
    if (buckets.size > 5_000) {
      for (const [k, b] of buckets) if (now - b.start >= WINDOW_MS) buckets.delete(k);
    }
    return true;
  }
  bucket.count += 1;
  return bucket.count <= limit;
}
