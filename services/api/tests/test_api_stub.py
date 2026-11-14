"""S0 stub behaviour through the real HTTP routes."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import DEMO_CODE

MAIN = [
    "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
    "I don't remember the name. I used it for a few days.",
    "I started using a new hand soap before this began.",
]
NO_MATCH = "My scalp feels uncomfortable. I don't know when it began."


def rid() -> str:
    return str(uuid.uuid4())


def create(client: TestClient) -> tuple[str, dict]:
    res = client.post("/v1/sessions", headers=DEMO_CODE,
                      json={"request_id": rid(), "collection_id": "synthetic-demo-v1"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["snapshot"]["revision"] == 0 and body["snapshot"]["brief"] is None
    assert body["session_token"] not in str(body["snapshot"])  # token never embedded in snapshot JSON
    return body["session_id"], {"Authorization": f"Bearer {body['session_token']}"}


def say(client, sid, auth, revision, text, reply_to=None) -> dict:
    turn = {"turn_id": f"t-{uuid.uuid4()}", "role": "patient", "origin": "typed",
            "text": text, "reply_to_question_id": reply_to}
    res = client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                      json={"request_id": rid(), "expected_revision": revision, "turns": [turn]})
    assert res.status_code == 200, res.text
    return res.json()


def advance(client, sid, auth, revision) -> dict:
    res = client.post(f"/v1/sessions/{sid}/advance", headers=auth,
                      json={"request_id": rid(), "expected_revision": revision})
    assert res.status_code == 200, res.text
    return res.json()


def assert_patient_quotes_resolve(snapshot: dict) -> None:
    turns = {t["turn_id"]: t["text"] for t in snapshot["turns"]}

    def walk(value):
        if isinstance(value, dict):
            if value.get("source_type") == "patient_turn":
                assert value["source_id"] in turns, value
                assert value["quote"] in turns[value["source_id"]], value
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(snapshot)


def test_health_and_docs(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_demo_code_gate(client: TestClient) -> None:
    assert client.get("/v1/readiness").status_code == 403
    bad = client.get("/v1/collections", headers={"X-Demo-Access-Code": "wrong"})
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "BAD_DEMO_CODE"
    ready = client.get("/v1/readiness", headers=DEMO_CODE).json()
    assert ready == {"storage": "memory", "extractor": "fixture", "collection_mode": "synthetic",
                     "loaded_cases": 3, "ready": True}


def test_main_typed_flow_to_confirmation(client: TestClient) -> None:
    sid, auth = create(client)
    snap = say(client, sid, auth, 0, MAIN[0])
    assert snap["revision"] == 1 and snap["modes"] == {"storage": "memory", "extractor": "fixture"}
    first = advance(client, sid, auth, 1)
    assert first["action"] == "ask" and first["question"]["template_id"] == "cream_details_v1"
    assert_patient_quotes_resolve(first["snapshot"])

    snap = say(client, sid, auth, 1, MAIN[1], reply_to=first["question"]["question_id"])
    second = advance(client, sid, auth, snap["revision"])
    assert second["question"]["template_id"] == "exposure_context_v1"

    snap = say(client, sid, auth, 2, MAIN[2], reply_to=second["question"]["question_id"])
    third = advance(client, sid, auth, snap["revision"])
    assert third["action"] == "ready_to_confirm"
    history = third["snapshot"]["search_history"]
    assert [s["ranked_case_ids"] for s in history] == [["SYN-A", "SYN-B"], ["SYN-A", "SYN-B"], ["SYN-A"]]
    assert_patient_quotes_resolve(third["snapshot"])

    confirmed = client.post(f"/v1/sessions/{sid}/confirm", headers=auth,
                            json={"request_id": rid(), "expected_revision": 3}).json()
    assert confirmed["state"] == "confirmed" and confirmed["confirmed_revision"] == confirmed["revision"] == 3

    note = client.post(f"/v1/sessions/{sid}/clinician-notes", headers=auth,
                       json={"request_id": rid(), "expected_revision": 3,
                             "note_text": "Fictional note.", "author_label": "Demo clinician"}).json()
    after = client.get(f"/v1/sessions/{sid}", headers=auth).json()
    assert after["clinician_notes"][0]["note_id"] == note["note_id"]
    assert after["facts"] == confirmed["facts"]  # note never alters patient facts


def test_no_match_still_has_brief(client: TestClient) -> None:
    sid, auth = create(client)
    say(client, sid, auth, 0, NO_MATCH)
    result = advance(client, sid, auth, 1)
    latest = result["snapshot"]["search_history"][-1]
    assert latest["cards"] == [] and latest["no_match_reason"] == "no_comparable_cases"
    assert result["snapshot"]["brief"]["summary_items"]


def test_new_patient_content_invalidates_confirmation(client: TestClient) -> None:
    sid, auth = create(client)
    say(client, sid, auth, 0, NO_MATCH)
    advance(client, sid, auth, 1)
    client.post(f"/v1/sessions/{sid}/confirm", headers=auth, json={"request_id": rid(), "expected_revision": 1})
    late = say(client, sid, auth, 1, "Late fictional transcript.")
    assert late["confirmed_revision"] is None and late["state"] == "intake" and late["revision"] == 2


def test_confirm_requires_processed_search(client: TestClient) -> None:
    sid, auth = create(client)
    say(client, sid, auth, 0, NO_MATCH)
    res = client.post(f"/v1/sessions/{sid}/confirm", headers=auth, json={"request_id": rid(), "expected_revision": 1})
    assert res.status_code == 409 and res.json()["error"]["code"] == "NOT_READY_TO_CONFIRM"


def test_stale_revision_rejected_without_change(client: TestClient) -> None:
    sid, auth = create(client)
    say(client, sid, auth, 0, NO_MATCH)
    request_id = rid()
    turn = {"turn_id": "t-stale", "role": "patient", "origin": "typed", "text": "x", "reply_to_question_id": None}
    res = client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                      json={"request_id": request_id, "expected_revision": 0, "turns": [turn]})
    assert res.status_code == 409
    assert res.json() == {"error": {"code": "REVISION_CONFLICT", "message": "Reload the current session.",
                                    "retryable": False}, "request_id": request_id}
    assert client.get(f"/v1/sessions/{sid}", headers=auth).json()["revision"] == 1


def test_retry_is_idempotent_and_mismatch_conflicts(client: TestClient) -> None:
    sid, auth = create(client)
    body = {"request_id": rid(), "expected_revision": 0,
            "turns": [{"turn_id": "t-1", "role": "patient", "origin": "typed", "text": NO_MATCH,
                       "reply_to_question_id": None}]}
    first = client.post(f"/v1/sessions/{sid}/turns", headers=auth, json=body).json()
    again = client.post(f"/v1/sessions/{sid}/turns", headers=auth, json=body).json()
    assert first == again and len(again["turns"]) == 1
    body["turns"][0]["text"] = "different"
    assert client.post(f"/v1/sessions/{sid}/turns", headers=auth, json=body).status_code == 409


def test_text_without_supported_details_gets_an_honest_insufficient_brief(client: TestClient) -> None:
    sid, auth = create(client)
    say(client, sid, auth, 0, "Something unrelated that names no symptom or body site.")
    res = client.post(f"/v1/sessions/{sid}/advance", headers=auth, json={"request_id": rid(), "expected_revision": 1})
    assert res.status_code == 200
    body = res.json()
    latest = body["snapshot"]["search_history"][-1]
    assert latest["cards"] == [] and latest["no_match_reason"] == "insufficient_information"
    assert body["snapshot"]["facts"] == []  # nothing invented
    missing = [i["text"] for i in body["snapshot"]["brief"]["unresolved_items"] if i["status"] == "missing"]
    assert "Body site not provided." in missing and "Symptom not provided." in missing


def test_session_auth(client: TestClient) -> None:
    sid, _ = create(client)
    other_sid, other_auth = create(client)
    assert client.get(f"/v1/sessions/{sid}").status_code == 401
    assert client.get(f"/v1/sessions/{sid}", headers={"Authorization": "Bearer nope"}).status_code == 404
    assert client.get(f"/v1/sessions/{sid}", headers=other_auth).status_code == 404  # no cross-session access
    assert client.get(f"/v1/sessions/{other_sid}", headers=other_auth).status_code == 200


def test_create_session_retry_returns_same_session(client: TestClient) -> None:
    body = {"request_id": rid(), "collection_id": "synthetic-demo-v1"}
    a = client.post("/v1/sessions", headers=DEMO_CODE, json=body).json()
    b = client.post("/v1/sessions", headers=DEMO_CODE, json=body).json()
    assert a["session_id"] == b["session_id"] and a["session_token"] == b["session_token"]
    assert client.post("/v1/sessions", headers=DEMO_CODE,
                       json={"request_id": rid(), "collection_id": "published-v1"}).status_code == 404


def test_validation_error_does_not_echo_input(client: TestClient) -> None:
    sid, auth = create(client)
    res = client.post(f"/v1/sessions/{sid}/turns", headers=auth,
                      json={"request_id": rid(), "expected_revision": 0, "turns": [{"text": "secret-ish"}]})
    assert res.status_code == 422 and "secret-ish" not in res.text
