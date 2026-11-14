"""Smoke-check a running API with one labelled fictional encounter.

    $env:API_URL="http://localhost:8000"; $env:DEMO_ACCESS_CODE="..."
    python -m scripts.smoke

Never prints the session token. Reports the storage/extractor modes the API
actually returned; it does not claim Exasol unless the API reports it.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx

FICTIONAL_TEXT = "My scalp feels uncomfortable. I don't know when it began."


def main() -> int:
    base = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
    code = os.getenv("DEMO_ACCESS_CODE") or "local-demo"
    with httpx.Client(base_url=base, timeout=15) as client:
        health = client.get("/health")
        print(f"health: {health.status_code} {health.json()}")
        readiness = client.get("/v1/readiness", headers={"X-Demo-Access-Code": code})
        print(f"readiness: {readiness.status_code} {readiness.json()}")
        if readiness.status_code != 200:
            return 1
        collections = client.get("/v1/collections", headers={"X-Demo-Access-Code": code}).json()["collections"]
        if not collections:
            print("smoke: no collections available", file=sys.stderr)
            return 1
        created = client.post(
            "/v1/sessions",
            headers={"X-Demo-Access-Code": code},
            json={"request_id": str(uuid.uuid4()), "collection_id": collections[0]["collection_id"]},
        )
        created.raise_for_status()
        body = created.json()
        session_id, auth = body["session_id"], {"Authorization": f"Bearer {body['session_token']}"}
        turn = {"turn_id": f"smoke-{uuid.uuid4()}", "role": "patient", "origin": "typed",
                "text": FICTIONAL_TEXT, "reply_to_question_id": None}
        snap = client.post(f"/v1/sessions/{session_id}/turns", headers=auth,
                           json={"request_id": str(uuid.uuid4()), "expected_revision": 0, "turns": [turn]})
        snap.raise_for_status()
        adv = client.post(f"/v1/sessions/{session_id}/advance", headers=auth,
                          json={"request_id": str(uuid.uuid4()), "expected_revision": snap.json()["revision"]})
        adv.raise_for_status()
        result = adv.json()
        latest = result["snapshot"]["search_history"][-1]
        print(f"session: {session_id} (fictional smoke encounter)")
        print(f"modes: {result['snapshot']['modes']}  collection: {result['snapshot']['collection']['mode']}")
        print(f"action: {result['action']}  cards: {len(latest['cards'])}  no_match: {latest['no_match_reason']}")
        reread = client.get(f"/v1/sessions/{session_id}", headers=auth)
        reread.raise_for_status()
        print(f"read-back revision: {reread.json()['revision']}")
    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
