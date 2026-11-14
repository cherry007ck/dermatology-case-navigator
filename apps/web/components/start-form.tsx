"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiRequestError, getApiClient, newRequestId } from "@/lib/api/client";
import type { Collection } from "@/lib/api/types";
import { saveSessionToken } from "@/lib/session-store";

import { Notice } from "./status";

export function StartForm() {
  const router = useRouter();
  const api = getApiClient();
  const [code, setCode] = useState("");
  const [collections, setCollections] = useState<Collection[] | null>(null);
  const [collectionId, setCollectionId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadCollections(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.listCollections(code);
      setCollections(res.collections);
      setCollectionId(res.collections[0]?.collection_id ?? "");
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : "Could not load collections.");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.createSession(code, { request_id: newRequestId(), collection_id: collectionId });
      saveSessionToken(res.session_id, res.session_token);
      router.push(`/intake/${encodeURIComponent(res.session_id)}`);
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : "Could not start the intake.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={loadCollections} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-1">
          <Label htmlFor="demo-code" className="text-base">
            Demo access code
          </Label>
          <Input
            id="demo-code"
            type="password"
            autoComplete="off"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="h-11 text-base"
            required
          />
        </div>
        <Button type="submit" size="lg" variant="outline" className="h-11 px-4 text-base" disabled={busy || !code}>
          Load collections
        </Button>
      </form>

      {collections && collections.length === 0 && (
        <Notice tone="warning">No collection is available on this server. Published evidence is not loaded.</Notice>
      )}

      {collections && collections.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="text-base font-medium">Source collection</legend>
          {collections.map((c) => (
            <label key={c.collection_id} className="flex items-start gap-3 rounded-xl border bg-card p-3">
              <input
                type="radio"
                name="collection"
                className="mt-1 size-4 accent-[var(--primary)]"
                value={c.collection_id}
                checked={collectionId === c.collection_id}
                onChange={() => setCollectionId(c.collection_id)}
              />
              <span>
                <span className="font-medium">
                  {c.mode === "synthetic" ? "Synthetic — fictional demonstration cases" : "Published — source-reviewed cases"}
                </span>
                <span className="block text-sm text-muted-foreground">
                  {c.collection_id} · {c.case_count} cases ·{" "}
                  {c.mode === "synthetic"
                    ? `${c.source_review_count} fixture consistency checks`
                    : `${c.source_review_count} developer source reviews`}{" "}
                  · {c.clinical_reviewed ? "clinically reviewed" : "not clinically reviewed"}
                </span>
              </span>
            </label>
          ))}
          <Button size="lg" className="h-11 px-5 text-base" onClick={start} disabled={busy || !collectionId}>
            Start intake
          </Button>
        </fieldset>
      )}

      {error && <Notice tone="error">{error}</Notice>}
    </div>
  );
}
