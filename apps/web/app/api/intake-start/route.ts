import type { NextRequest } from "next/server";
import { allowRequest } from "@/lib/server/rate-limit";

const headers = { "Cache-Control": "no-store" };
function failure(status: number, message: string) {
  return Response.json(
    {
      error: { code: "INTAKE_UNAVAILABLE", message, retryable: status >= 500 },
    },
    { status, headers },
  );
}

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  let originHost: string | null = null;
  try {
    originHost = origin ? new URL(origin).host : null;
  } catch {
    return failure(403, "Request origin not allowed.");
  }
  if (
    !origin ||
    (origin !== request.nextUrl.origin && originHost !== host) ||
    request.headers.get("sec-fetch-site") === "cross-site"
  ) {
    return failure(403, "Request origin not allowed.");
  }
  const client =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  if (!allowRequest(`intake-start:${client}`, 10))
    return failure(429, "Too many requests. Please wait a minute and retry.");
  if (Number(request.headers.get("content-length") ?? 0) > 1024)
    return failure(413, "Request too large.");
  const raw = await request.text();
  if (raw.length > 1024) return failure(413, "Request too large.");
  let body: { request_id?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return failure(422, "Invalid request.");
  }
  if (
    !body ||
    typeof body.request_id !== "string" ||
    !/^[a-f0-9-]{36}$/i.test(body.request_id)
  )
    return failure(422, "Invalid request ID.");
  const base = (
    process.env.API_INTERNAL_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL
  )?.replace(/\/$/, "");
  const code = process.env.DEMO_ACCESS_CODE;
  if (!base || !code)
    return failure(
      503,
      "The intake service is not configured. Please contact the project administrator.",
    );
  try {
    const upstreamHeaders = {
      "Content-Type": "application/json",
      "X-Demo-Access-Code": code,
    };
    const response = await fetch(`${base}/v1/collections`, {
      headers: upstreamHeaders,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok)
      return failure(
        503,
        "The case collection is temporarily unavailable. Please retry.",
      );
    const data = (await response.json()) as {
      collections: { collection_id: string; mode: string }[];
    };
    const collection =
      data.collections.find((item) => item.mode === "published") ??
      data.collections[0];
    if (!collection)
      return failure(503, "No case collection is available yet.");
    const result = await fetch(`${base}/v1/sessions`, {
      method: "POST",
      headers: upstreamHeaders,
      body: JSON.stringify({
        request_id: body.request_id,
        collection_id: collection.collection_id,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!result.ok)
      return failure(
        result.status === 429 ? 429 : 503,
        "The intake could not be started. Please retry.",
      );
    return Response.json(await result.json(), { headers });
  } catch {
    return failure(
      503,
      "The intake service could not be reached. Please retry.",
    );
  }
}
