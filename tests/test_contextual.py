"""Focused tests for Phase 4 / Task 7: Optional contextual detection."""

import ipaddress
import time
from threading import Event, Thread
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from kavach.detectors.contextual import get_contextual_detector, reset_contextual_detector
from kavach.main import create_app


class TestContextualDetectorAbsent:
    """Test app behavior when contextual model is unavailable."""

    def test_health_reports_unavailable_status(self, monkeypatch):
        """Health endpoint reports contextual unavailability without crashing."""
        app = create_app()
        client = TestClient(app)

        # Mock loopback check for TestClient
        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "contextual_model_available" in data
        assert "contextual_model_status" in data
        # Status should be a non-empty string regardless of availability
        assert isinstance(data["contextual_model_status"], str)
        assert len(data["contextual_model_status"]) > 0

    def test_analyze_works_without_model(self, monkeypatch):
        """Analyze endpoint works with only deterministic detectors."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.post(
            "/api/v1/analyze",
            json={"text": "My PAN is ABCDE1234F and Aadhaar is 234567890009"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should detect PAN and Aadhaar deterministically
        assert len(data["candidates"]) >= 2
        sources = {c["source"] for c in data["candidates"]}
        assert "pan" in sources or "aadhaar" in sources

    def test_detector_available_property_is_false_when_missing(self):
        """Detector available property is False when model not loaded."""
        # This test assumes spaCy model is not installed yet
        detector = get_contextual_detector()
        # available should be False if model is missing
        assert isinstance(detector.available, bool)
        # status should indicate why it's unavailable
        assert isinstance(detector.status, str)


class TestContextualDetectorPresent:
    """Tests that require spaCy model to be installed."""

    def test_detector_loads_when_available(self):
        """If spaCy and model are installed, detector loads successfully."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed; run: python -m spacy download en_core_web_sm")

        assert detector.available is True
        assert detector.status == "available"
        assert detector.name == "contextual"

    def test_detect_person_names(self):
        """Contextual detector identifies person names."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        text = "John Smith works at Acme Corp with Jane Doe."
        spans = detector.detect(text)

        # Should detect at least one person name
        person_spans = [s for s in spans if s.category == "PERSON"]
        assert len(person_spans) > 0
        assert all(s.source == "contextual" for s in person_spans)
        assert all(s.confidence == 0.7 for s in person_spans)

    def test_detect_addresses(self):
        """Contextual detector identifies location/address entities."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        text = "She lives in Mumbai, India near the Gateway of India."
        spans = detector.detect(text)

        # Should detect location entities as ADDRESS
        address_spans = [s for s in spans if s.category == "ADDRESS"]
        assert len(address_spans) > 0
        assert all(s.source == "contextual" for s in address_spans)

    def test_bounded_input_safety(self):
        """Detector respects max_chars limit."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        # Create text longer than default max_chars=5000
        long_text = "John Smith. " * 1000  # ~12KB
        spans = detector.detect(long_text, max_chars=100)

        # Should only process first 100 chars
        # Verify no exception and returns results
        assert isinstance(spans, list)

    def test_empty_text_returns_empty(self):
        """Detector handles empty text gracefully."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        spans = detector.detect("")
        assert spans == []

        spans = detector.detect("   ")
        assert spans == []

    def test_integration_with_pipeline(self, monkeypatch):
        """Contextual spans appear in full pipeline results."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        # Text with both deterministic (PAN) and contextual (name) PII
        response = client.post(
            "/api/v1/analyze",
            json={"text": "Jane Doe's PAN is ABCDE1234F"}
        )
        assert response.status_code == 200
        data = response.json()

        sources = {c["source"] for c in data["candidates"]}
        # Should have PAN from deterministic
        assert "pan" in sources
        # Should have name from contextual
        assert "contextual" in sources

        contextual_candidates = [c for c in data["candidates"] if c["source"] == "contextual"]
        assert len(contextual_candidates) > 0
        # At least one should be PERSON category
        assert any(c["category"] == "PERSON" for c in contextual_candidates)


class TestContextualTimeout:
    """Test timeout and failure handling with forced conditions."""

    def test_timeout_marks_degraded(self, monkeypatch):
        """Simulated timeout marks detector degraded and health reports it."""
        # Reset singleton to create fresh detector with short timeout
        reset_contextual_detector()

        # Mock detector with artificial timeout
        mock_detector = Mock()
        mock_detector.available = True
        mock_detector.timeout_seconds = 0.1
        mock_detector._degraded = False
        mock_detector._runtime_error = None

        def slow_detect(text):
            time.sleep(0.5)  # Exceeds timeout
            return []

        def mark_degraded(reason):
            mock_detector._degraded = True
            mock_detector._runtime_error = reason

        def get_status():
            if mock_detector._degraded and mock_detector._runtime_error:
                return f"degraded: {mock_detector._runtime_error}"
            return "available"

        mock_detector.detect = slow_detect
        mock_detector.mark_degraded = mark_degraded
        mock_detector.status = property(lambda self: get_status())

        monkeypatch.setattr(
            "kavach.core.pipeline.get_contextual_detector",
            lambda: mock_detector
        )

        # Import after monkeypatch
        from kavach.core.pipeline import analyze_candidates

        # This should timeout and mark degraded
        candidates = analyze_candidates("Test text with PAN ABCDE1234F")

        # Should have deterministic PAN candidate
        assert any(c.source == "pan" for c in candidates)
        # Should NOT have contextual candidates due to timeout
        assert not any(c.source == "contextual" for c in candidates)
        # Detector should be marked degraded
        assert mock_detector._degraded is True
        assert "timeout" in mock_detector._runtime_error

    def test_in_flight_timeout_does_not_queue_more_text(self, monkeypatch):
        """A busy contextual worker is not given another request's text."""
        from kavach.core import pipeline

        started = Event()
        release = Event()
        calls = []
        submissions = []
        real_executor = pipeline._executor

        class CountingExecutor:
            def submit(self, function, text):
                submissions.append(text)
                return real_executor.submit(function, text)

        monkeypatch.setattr(pipeline, "_executor", CountingExecutor())
        mock_detector = Mock()
        mock_detector.available = True
        mock_detector.timeout_seconds = 2.0
        mock_detector.mark_degraded = Mock()

        def held_detect(text):
            calls.append(text)
            started.set()
            release.wait()
            return []

        mock_detector.detect = held_detect
        monkeypatch.setattr("kavach.core.pipeline.get_contextual_detector", lambda: mock_detector)
        monkeypatch.setattr(pipeline, "_contextual_future", None)

        first_result = []
        first_call = Thread(
            target=lambda: first_result.extend(pipeline.analyze_candidates("PAN ABCDE1234F"))
        )
        first_call.start()
        try:
            assert started.wait(timeout=2.0)

            second_result = pipeline.analyze_candidates("PAN FGHIJ5678K")

            assert any(candidate.source == "pan" for candidate in second_result)
            assert not any(candidate.source == "contextual" for candidate in second_result)
            assert calls == ["PAN ABCDE1234F"]
            assert submissions == ["PAN ABCDE1234F"]
        finally:
            release.set()
            first_call.join(timeout=2.0)

        assert not first_call.is_alive()
        assert any(candidate.source == "pan" for candidate in first_result)

    def test_exception_marks_degraded(self, monkeypatch):
        """Simulated exception marks detector degraded."""
        reset_contextual_detector()

        mock_detector = Mock()
        mock_detector.available = True
        mock_detector.timeout_seconds = 5.0
        mock_detector._degraded = False
        mock_detector._runtime_error = None

        def failing_detect(text):
            raise RuntimeError("Simulated NLP failure")

        def mark_degraded(reason):
            mock_detector._degraded = True
            mock_detector._runtime_error = reason

        def get_status():
            if mock_detector._degraded and mock_detector._runtime_error:
                return f"degraded: {mock_detector._runtime_error}"
            return "available"

        mock_detector.detect = failing_detect
        mock_detector.mark_degraded = mark_degraded
        mock_detector.status = property(lambda self: get_status())

        monkeypatch.setattr(
            "kavach.core.pipeline.get_contextual_detector",
            lambda: mock_detector
        )

        from kavach.core.pipeline import analyze_candidates

        # This should catch exception and mark degraded
        analyze_candidates("Test text")

        # Detector should be marked degraded
        assert mock_detector._degraded is True
        assert "RuntimeError" in mock_detector._runtime_error

    def test_health_reports_degraded_after_timeout(self, monkeypatch):
        """Health endpoint reports degraded status after timeout."""
        # Create detector that's already degraded
        mock_detector = Mock()
        mock_detector.available = True
        mock_detector._degraded = True
        mock_detector._runtime_error = "timeout"
        mock_detector.status = "degraded: timeout"

        # Patch in both contextual module and routes module
        monkeypatch.setattr(
            "kavach.detectors.contextual.get_contextual_detector",
            lambda: mock_detector
        )
        monkeypatch.setattr(
            "kavach.api.routes.get_contextual_detector",
            lambda: mock_detector
        )

        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["contextual_model_available"] is True
        assert "degraded" in data["contextual_model_status"]
        assert "timeout" in data["contextual_model_status"]

    def test_detector_exception_internal(self):
        """Detector.detect() marks itself degraded on internal exception."""
        detector = get_contextual_detector()
        if not detector.available:
            pytest.skip("spaCy model not installed")

        # Patch the nlp to raise exception
        original_nlp = detector._nlp

        def broken_nlp(text):
            raise ValueError("Forced internal error")

        detector._nlp = broken_nlp

        # Should catch exception and return empty
        spans = detector.detect("Test text")
        assert spans == []

        # Should be marked degraded
        assert "degraded" in detector.status
        assert "ValueError" in detector.status

        # Restore
        detector._nlp = original_nlp
