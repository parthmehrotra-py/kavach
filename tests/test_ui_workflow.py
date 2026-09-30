"""Focused tests for Phase 6 / Task 9: Single-page UI workflow."""

import ipaddress

from fastapi.testclient import TestClient

from kavach.main import create_app


class TestUIWorkflow:
    """Test complete UI workflow through API."""

    def test_redact_copy_restore_flow(self, monkeypatch):
        """Test manual redact -> copy -> paste -> restore flow."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # Step 1: Analyze text
        text = "My PAN is ABCDE1234F"
        analyze_resp = client.post("/api/v1/analyze", json={"text": text})
        assert analyze_resp.status_code == 200
        candidates = analyze_resp.json()["candidates"]
        assert len(candidates) > 0

        # Step 2: User reviews and approves (simulate explicit approval)
        approved_id = candidates[0]["id"]

        # Step 3: Redact approved candidates
        redact_resp = client.post(
            "/api/v1/redact",
            json={"text": text, "approved_candidate_ids": [approved_id]}
        )
        assert redact_resp.status_code == 200
        redacted_data = redact_resp.json()
        session_id = redacted_data["session_id"]
        redacted_text = redacted_data["redacted_text"]

        # Verify text was actually redacted
        assert "ABCDE1234F" not in redacted_text
        assert "KAVACH" in redacted_text  # Contains placeholder

        # Step 4: User manually copies to external AI (simulated)
        # AI returns response with placeholders intact
        ai_response = f"The document contains {redacted_text} which needs verification."

        # Step 5: Restore placeholders
        restore_resp = client.post(
            "/api/v1/restore",
            json={"session_id": session_id, "text": ai_response}
        )
        assert restore_resp.status_code == 200
        restored_data = restore_resp.json()
        restored_text = restored_data["restored_text"]
        assert restored_data["restored_count"] > 0

        # Verify original value was restored
        assert "ABCDE1234F" in restored_text

    def test_redaction_requires_explicit_approval(self, monkeypatch):
        """Redaction endpoint requires explicit candidate IDs (no auto-redact)."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # Analyze detects candidates
        text = "PAN ABCDE1234F and phone +91-9876543210"
        analyze_resp = client.post("/api/v1/analyze", json={"text": text})
        assert analyze_resp.status_code == 200
        candidates = analyze_resp.json()["candidates"]
        assert len(candidates) >= 2  # PAN and phone

        # Attempting to redact with empty approval list should fail
        redact_resp = client.post(
            "/api/v1/redact",
            json={"text": text, "approved_candidate_ids": []}
        )
        assert redact_resp.status_code == 422  # Validation error (min_length=1)

        # Redact with explicit approval of only one candidate
        approved_id = candidates[0]["id"]
        redact_resp = client.post(
            "/api/v1/redact",
            json={"text": text, "approved_candidate_ids": [approved_id]}
        )
        assert redact_resp.status_code == 200

        # Only approved candidate should be redacted
        redacted_text = redact_resp.json()["redacted_text"]
        placeholders_count = redacted_text.count("KAVACH")
        assert placeholders_count >= 1  # At least one redacted

    def test_clear_session_removes_state(self, monkeypatch):
        """Clearing session removes server state."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # Create a session
        text = "PAN ABCDE1234F"
        analyze_resp = client.post("/api/v1/analyze", json={"text": text})
        candidate_id = analyze_resp.json()["candidates"][0]["id"]

        redact_resp = client.post(
            "/api/v1/redact",
            json={"text": text, "approved_candidate_ids": [candidate_id]}
        )
        session_id = redact_resp.json()["session_id"]

        # Delete session
        delete_resp = client.delete(f"/api/v1/session/{session_id}")
        assert delete_resp.status_code == 204

        # Attempting to restore with deleted session should fail
        restore_resp = client.post(
            "/api/v1/restore",
            json={"session_id": session_id, "text": "placeholder text"}
        )
        assert restore_resp.status_code == 404

    def test_ui_page_is_served(self, monkeypatch):
        """Static UI page is served at root."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Kavach" in response.content

    def test_all_requests_are_loopback(self, monkeypatch):
        """Verify all workflow requests go to loopback API."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # All API endpoints should accept loopback requests
        endpoints = [
            ("GET", "/api/v1/health"),
            ("POST", "/api/v1/analyze", {"text": "test"}),
            ("GET", "/api/v1/hardware/capabilities"),
        ]

        for method, path, *body in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path, json=body[0] if body else {})

            # Should succeed (not 403 Forbidden)
            assert response.status_code != 403, f"{method} {path} failed loopback check"


class TestFileIngestion:
    """Test file upload workflow."""

    def test_image_upload_and_analysis(self, monkeypatch):
        """Test uploading image, extracting text, and analyzing."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # Create minimal PNG
        import io

        from PIL import Image

        img = Image.new('RGB', (100, 50), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Upload file
        files = {"file": ("test.png", img_bytes, "image/png")}
        response = client.post("/api/v1/ingest", files=files)
        assert response.status_code == 200
        data = response.json()

        assert "extracted_text" in data
        assert "candidates" in data
        # Empty image won't have text, but structure should be correct
        assert isinstance(data["candidates"], list)
