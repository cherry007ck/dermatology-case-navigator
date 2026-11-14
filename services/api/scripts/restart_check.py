"""Prove a saved encounter survives an API restart (run against a live API, two phases).

    python -m scripts.restart_check write    # create a fictional encounter, append a turn, advance
    (restart the API process)
    python -m scripts.restart_check verify   # re-read it through the restarted API

Uses API_URL and DEMO_ACCESS_CODE from the environment. The state file (system temp folder)
holds only the creation request ID, session ID and expected values; never the session token.
``verify`` regains access by retrying the original create-session request: the API returns the same
session and re-derives the same token only if the idempotency record survived in storage.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

STATE = Path(tempfile.gettempdir()) / "dcn-restart-check.json"
FICTIONAL_TEXT = "My hands have been itchy for weeks. I tried a cream, but it didn't help."


def _client() -> tuple[httpx.Client, dict]:
    base = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
    code = os.getenv("DEMO_ACCESS_CODE") or "local-demo"
    return httpx.Client(base_url=base, timeout=60), {"X-Demo-Access-Code": code}


def _create(client: httpx.Client, demo: dict, request_id: str, collection_id: str) -> dict:
    res = client.post("/v1/sessions", headers=demo, json={"request_id": request_id, "collection_id": collection_id})
    res.raise_for_status()
    return res.json()


def write() -> int:
    client, demo = _client()
    readiness = client.get("/v1/readiness", headers=demo).json()
    print(f"readiness: {readiness}")
    collection_id = client.get("/v1/collections", headers=demo).json()["collections"][0]["collection_id"]
    request_id = str(uuid.uuid4())
    created = _create(client, demo, request_id, collection_id)
    sid, auth = created["session_id"], {"Authorization": f"Bearer {created['session_token']}"}
    turn = {"turn_id": f"restart-{uuid.uuid4()}", "role": "patient", "origin": "typed",
            "text": FICTIONAL_TEXT, "reply_to_question_id": None}
    client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                json={"request_id": str(uuid.uuid4()), "expected_revision": 0, "turns": [turn]}).raise_for_status()
    adv = client.post(f"/v1/sessions/{sid}/advance", headers=auth,
                      json={"request_id": str(uuid.uuid4()), "expected_revision": 1})
    adv.raise_for_status()
    snap = adv.json()["snapshot"]
    expected = {
        "request_id": request_id, "collection_id": collection_id, "session_id": sid,
        "revision": snap["revision"], "state": snap["state"], "turn_ids": [t["turn_id"] for t in snap["turns"]],
        "search_ids": [s["search_id"] for s in snap["search_history"]], "storage": snap["modes"]["storage"],
    }
    STATE.write_text(json.dumps(expected), encoding="utf-8")
    print(f"write: session {sid} revision {expected['revision']} state {expected['state']} "
          f"turns {len(expected['turn_ids'])} searches {len(expected['search_ids'])} storage {expected['storage']}")
    print("write: done. Restart the API, then run: python -m scripts.restart_check verify")
    return 0


def verify() -> int:
    if not STATE.exists():
        print("verify: run the write phase first", file=sys.stderr)
        return 2
    expected = json.loads(STATE.read_text(encoding="utf-8"))
    client, demo = _client()
    again = _create(client, demo, expected["request_id"], expected["collection_id"])
    if again["session_id"] != expected["session_id"]:
        print("verify: FAILED - create retry returned a different session (idempotency record lost)")
        return 1
    snap = client.get(f"/v1/sessions/{again['session_id']}",
                      headers={"Authorization": f"Bearer {again['session_token']}"})
    if snap.status_code != 200:
        print(f"verify: FAILED - session read returned {snap.status_code}")
        return 1
    body = snap.json()
    actual = {
        "revision": body["revision"], "state": body["state"], "turn_ids": [t["turn_id"] for t in body["turns"]],
        "search_ids": [s["search_id"] for s in body["search_history"]], "storage": body["modes"]["storage"],
    }
    problems = [k for k, v in actual.items() if v != expected[k]]
    print(f"verify: session {expected['session_id']} revision {actual['revision']} state {actual['state']} "
          f"turns {len(actual['turn_ids'])} searches {len(actual['search_ids'])} storage {actual['storage']}")
    if problems:
        print(f"verify: FAILED - mismatched {problems}")
        return 1
    if actual["storage"] != "exasol":
        print("verify: FAILED - API is not in Exasol mode; memory cannot survive a restart")
        return 1
    STATE.unlink()
    print("verify: PASS - encounter, turns, search history and idempotency record survived the restart")
    return 0


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit({"write": write, "verify": verify}.get(phase, lambda: (print(__doc__), 2)[1])())
