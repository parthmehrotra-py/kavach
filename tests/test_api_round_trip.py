"""Focused end-to-end tests for the local API round trip."""

import ipaddress

from fastapi.testclient import TestClient

from kavach.main import create_app


def test_analyze_redact_restore_and_delete(monkeypatch):
    app = create_app()
    client = TestClient(app)
    real_ip_address = ipaddress.ip_address

    def testclient_loopback(host: str):
        return real_ip_address("127.0.0.1" if host == "testclient" else host)

    monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

    text = "PAN ABCDE1234F"
    analysis = client.post("/api/v1/analyze", json={"text": text})
    assert analysis.status_code == 200
    candidate_id = analysis.json()["candidates"][0]["id"]

    redaction = client.post(
        "/api/v1/redact",
        json={"text": text, "approved_candidate_ids": [candidate_id]},
    )
    assert redaction.status_code == 200
    redacted = redaction.json()
    assert "ABCDE1234F" not in redacted["redacted_text"]
    token = redacted["replacements"][0]["token"]

    restoration = client.post(
        "/api/v1/restore",
        json={"session_id": redacted["session_id"], "text": f"Answer: {token}"},
    )
    assert restoration.status_code == 200
    assert restoration.json()["restored_text"] == "Answer: ABCDE1234F"

    deleted = client.delete(f"/api/v1/session/{redacted['session_id']}")
    assert deleted.status_code == 204
    missing = client.post(
        "/api/v1/restore",
        json={"session_id": redacted["session_id"], "text": f"Answer: {token}"},
    )
    assert missing.status_code == 404


def test_invalid_approval_and_oversized_body_are_rejected(monkeypatch):
    app = create_app()
    client = TestClient(app)
    real_ip_address = ipaddress.ip_address

    def testclient_loopback(host: str):
        return real_ip_address("127.0.0.1" if host == "testclient" else host)

    monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

    invalid_approval = client.post(
        "/api/v1/redact",
        json={"text": "PAN ABCDE1234F", "approved_candidate_ids": ["fake_999"]},
    )
    assert invalid_approval.status_code == 400

    oversized = client.post(
        "/api/v1/analyze",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "10485761"},
    )
    assert oversized.status_code == 413
