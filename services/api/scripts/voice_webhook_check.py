"""Exercise the backend half of the voice loop against a running API, exactly as the ElevenLabs
`advance_intake` tool and the browser would. Run it locally or against the public API.

    python -m scripts.voice_webhook_check            # API_URL defaults to http://localhost:8000

Steps:
1. Create a fictional session.
2. Issue a voice binding (as the Next.js /api/voice-session route does).
3. Store a voice_transcript patient turn (as the browser does).
4. POST /v1/voice/advance with X-Tool-Secret and X-Voice-Binding (as the agent tool does).
5. Store the spoken answer, advance again, and read the updated patient review.

It also checks that the webhook rejects missing headers. It proves the backend-approved
question and the stored answer, but NOT speech recognition or text-to-speech: that needs the
configured agent and a microphone. DEMO_ACCESS_CODE and VOICE_TOOL_SECRET come from the
environment or services/api/.env and are never printed; neither is the binding token.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx
from dotenv import load_dotenv

from app.config import API_ROOT


def main() -> int:
    load_dotenv(API_ROOT / ".env", override=False)
    base = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
    demo = {"X-Demo-Access-Code": os.getenv("DEMO_ACCESS_CODE") or "local-demo"}
    secret = os.getenv("VOICE_TOOL_SECRET", "")
    ok = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")

    with httpx.Client(base_url=base, timeout=120) as c:
        ready = c.get("/v1/readiness", headers=demo).json()
        check("API modes", ready.get("ready") is True, f"{ready}")
        collection = c.get("/v1/collections", headers=demo).json()["collections"][0]["collection_id"]
        created = c.post("/v1/sessions", headers=demo, json={"request_id": str(uuid.uuid4()), "collection_id": collection}).json()
        sid, auth = created["session_id"], {"Authorization": f"Bearer {created['session_token']}"}
        binding = c.post(f"/v1/sessions/{sid}/voice-binding", headers=auth,
                         json={"request_id": str(uuid.uuid4()), "expected_revision": 0})
        check("voice binding issued", binding.status_code == 200, f"HTTP {binding.status_code}")
        token = binding.json().get("binding_token", "")
        tool = {"X-Tool-Secret": secret, "X-Voice-Binding": token}

        noauth = c.post("/v1/voice/advance", json={})
        check("webhook rejects missing headers", noauth.status_code == 401, f"HTTP {noauth.status_code}")
        wrong = c.post("/v1/voice/advance", json={}, headers={**tool, "X-Tool-Secret": "wrong"})
        check("webhook rejects a wrong tool secret", wrong.status_code == 401, f"HTTP {wrong.status_code}")

        def spoken(text: str, rev: int, reply_to: str | None) -> dict:
            r = c.post(f"/v1/sessions/{sid}/turns", headers=auth, json={
                "request_id": str(uuid.uuid4()), "expected_revision": rev,
                "turns": [{"turn_id": f"voice-{uuid.uuid4()}", "role": "patient", "origin": "voice_transcript",
                           "text": text, "reply_to_question_id": reply_to}]})
            r.raise_for_status()
            adv = c.post("/v1/voice/advance", json={"ignored": "the body is never used"}, headers=tool)
            return {"status": adv.status_code, **(adv.json() if adv.headers.get("content-type", "").startswith("application/json") else {})}

        first = spoken("Um, so my face is itchy.", 0, None)
        check("webhook returns a backend-approved question", first.get("action") == "ask" and bool(first.get("question_text")),
              f"{first.get('action')}: {first.get('question_text')!r}")
        again = c.post("/v1/voice/advance", json={}, headers=tool).json()
        check("duplicate tool call does not ask a second question", again.get("question_id") == first.get("question_id"))
        snap = c.get(f"/v1/sessions/{sid}", headers=auth).json()
        second = spoken("A few days, I think.", snap["revision"], None)
        check("stored spoken answer leads to ready_to_confirm", second.get("action") == "ready_to_confirm",
              f"{second.get('action')}: {second.get('spoken_message')!r}")
        snap = c.get(f"/v1/sessions/{sid}", headers=auth).json()
        brief = snap.get("brief") or {}
        check("patient review updated at the current revision", brief.get("patient_revision") == snap["revision"],
              f"revision {snap['revision']}, summary {[i['text'] for i in brief.get('summary_items', [])]}")
        check("answer linked to the question", [q["status"] for q in snap["questions"]] == ["answered"])
        check("no case content in the voice responses", all(k in ("status", "action", "question_id", "question_text", "spoken_message")
                                                             for k in {**first, **second}))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
