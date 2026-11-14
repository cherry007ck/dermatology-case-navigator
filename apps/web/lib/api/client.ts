// One typed API client. Components call `getApiClient()` and never know whether
// the transport is the live FastAPI backend or the labelled fixture mock.
import { createMockTransport } from "@/mocks/mock-transport";
import { ApiRequestError, type ApiMode, type ApiTransport } from "./transport";
import type { ApiErrorResponse } from "./types";

export { ApiRequestError, type ApiMode, type ApiTransport };

function createHttpTransport(baseUrl: string): ApiTransport {
  async function call<T>(method: "GET" | "POST", path: string, headers: Record<string, string>, body?: unknown) {
    let res: Response;
    try {
      res = await fetch(`${baseUrl}${path}`, {
        method,
        headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        cache: "no-store",
      });
    } catch {
      throw new ApiRequestError(0, "NETWORK_UNAVAILABLE", "The API could not be reached. Check your connection and retry.", true);
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      if (data && typeof data === "object" && "error" in data) throw ApiRequestError.fromBody(res.status, data as ApiErrorResponse);
      throw new ApiRequestError(res.status, "HTTP_ERROR", "The API returned an unexpected response.", res.status >= 500);
    }
    return data as T;
  }
  const demo = (code: string) => ({ "X-Demo-Access-Code": code });
  const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });
  const enc = encodeURIComponent;
  return {
    mode: "live",
    readiness: (code) => call("GET", "/v1/readiness", demo(code)),
    listCollections: (code) => call("GET", "/v1/collections", demo(code)),
    createSession: (code, body) => call("POST", "/v1/sessions", demo(code), body),
    getSession: (id, t) => call("GET", `/v1/sessions/${enc(id)}`, bearer(t)),
    appendTurns: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/turns`, bearer(t), body),
    advance: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/advance`, bearer(t), body),
    skip: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/skip`, bearer(t), body),
    confirm: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/confirm`, bearer(t), body),
    correct: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/corrections`, bearer(t), body),
    addClinicianNote: (id, t, body) => call("POST", `/v1/sessions/${enc(id)}/clinician-notes`, bearer(t), body),
  };
}

/** Explicit mode switch. Unset means mock, which the UI always labels. */
export function getApiMode(): ApiMode {
  return process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";
}

let client: ApiTransport | null = null;

export function getApiClient(): ApiTransport {
  if (!client) {
    client =
      getApiMode() === "live"
        ? createHttpTransport((process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, ""))
        : createMockTransport();
  }
  return client;
}

export function newRequestId(): string {
  return crypto.randomUUID();
}
