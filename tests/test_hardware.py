"""Focused tests for Phase 5 / Task 8: Hardware capabilities and benchmark."""

import ipaddress
from types import SimpleNamespace

from fastapi.testclient import TestClient

from kavach.hardware.capabilities import get_capabilities
from kavach.hardware.providers import Provider, set_provider
from kavach.main import create_app


class TestCapabilities:
    """Test hardware capability detection."""

    def test_capabilities_reports_architecture(self):
        """Capabilities include architecture and platform."""
        caps = get_capabilities()
        assert caps.architecture in ("AMD64", "x86_64", "ARM64", "aarch64")
        assert caps.platform_name in ("Windows", "Linux", "Darwin")

    def test_cpu_always_available(self):
        """CPU is always reported as available (baseline)."""
        caps = get_capabilities()
        assert caps.cpu_available is True

    def test_amd_npu_status_is_truthful(self):
        """AMD NPU status includes reason."""
        caps = get_capabilities()
        assert isinstance(caps.amd_npu_available, bool)
        assert isinstance(caps.amd_npu_reason, str)
        assert len(caps.amd_npu_reason) > 0

    def test_x86_architecture_does_not_claim_amd_vendor(self, monkeypatch):
        """An x86-64 architecture alone does not identify the CPU vendor."""
        from kavach.hardware.capabilities import detect_capabilities

        monkeypatch.setattr("kavach.hardware.capabilities.platform.machine", lambda: "AMD64")

        caps = detect_capabilities()

        assert caps.amd_npu_available is False
        assert "x86-64 architecture detected" in caps.amd_npu_reason
        assert "AMD NPU runtime not verified" in caps.amd_npu_reason
        assert "AMD CPU detected" not in caps.amd_npu_reason

    def test_snapdragon_always_unverified(self):
        """Snapdragon is reported as unverified until tested on real hardware."""
        caps = get_capabilities()
        assert caps.snapdragon_available is False
        assert caps.snapdragon_reason == "unverified"


class TestProviders:
    """Test provider selection and fallback."""

    def test_cpu_provider_always_works(self):
        """CPU provider is always available without fallback."""
        provider = set_provider(Provider.CPU)
        assert provider.requested == Provider.CPU
        assert provider.actual == Provider.CPU
        assert provider.is_fallback is False
        assert provider.fallback_reason is None

    def test_amd_npu_fallback_reason(self):
        """Requesting AMD NPU provides explicit fallback reason if unavailable."""
        caps = get_capabilities()
        provider = set_provider(Provider.AMD_NPU)

        if caps.amd_npu_available:
            assert provider.actual == Provider.AMD_NPU
            assert provider.is_fallback is False
        else:
            # Falls back to CPU
            assert provider.actual == Provider.CPU
            assert provider.is_fallback is True
            assert provider.fallback_reason is not None
            assert len(provider.fallback_reason) > 0

    def test_snapdragon_falls_back_to_cpu(self):
        """Requesting Snapdragon falls back to CPU with 'unverified' reason."""
        provider = set_provider(Provider.SNAPDRAGON)
        assert provider.requested == Provider.SNAPDRAGON
        assert provider.actual == Provider.CPU
        assert provider.is_fallback is True
        assert provider.fallback_reason == "unverified"


class TestBenchmark:
    """Test benchmark endpoint."""

    def test_runtime_label_reflects_contextual_model_availability(self, monkeypatch):
        """Without the optional model, benchmark reports deterministic runtime only."""
        from kavach.hardware.benchmark import run_detection_benchmark

        monkeypatch.setattr(
            "kavach.hardware.benchmark.get_contextual_detector",
            lambda: SimpleNamespace(available=False),
        )

        result = run_detection_benchmark(repetitions=1, text_samples=["Synthetic sample"])

        assert result.runtime == "deterministic"

    def test_benchmark_returns_measurements(self, monkeypatch):
        """Benchmark returns measured elapsed time and labels."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.post("/api/v1/benchmark", json={"repetitions": 5})
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "method" in data
        assert "workload_description" in data
        assert "repetitions" in data
        assert data["repetitions"] == 5
        assert "provider" in data
        assert "runtime" in data
        assert "device_label" in data
        assert "elapsed_seconds" in data

        # Elapsed time must be measured (not zero or hardcoded)
        assert data["elapsed_seconds"] > 0

        # Provider must be one of valid values
        assert data["provider"] in ("cpu", "amd-npu", "snapdragon")

        # Device label should include platform info
        assert len(data["device_label"]) > 0

    def test_benchmark_respects_repetitions(self, monkeypatch):
        """Benchmark respects requested repetitions."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.post("/api/v1/benchmark", json={"repetitions": 1})
        assert response.status_code == 200
        data = response.json()
        assert data["repetitions"] == 1

    def test_hardware_capabilities_endpoint(self, monkeypatch):
        """Hardware capabilities endpoint returns detection results."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.get("/api/v1/hardware/capabilities")
        assert response.status_code == 200
        data = response.json()

        assert "architecture" in data
        assert "platform_name" in data
        assert "cpu_available" in data
        assert data["cpu_available"] is True
        assert "amd_npu_available" in data
        assert "amd_npu_reason" in data
        assert "snapdragon_available" in data
        assert data["snapdragon_available"] is False
        assert data["snapdragon_reason"] == "unverified"

    def test_provider_status_endpoint(self, monkeypatch):
        """Provider status endpoint returns current selection."""
        app = create_app()
        client = TestClient(app)

        real_ip_address = ipaddress.ip_address

        def testclient_loopback(host: str):
            return real_ip_address("127.0.0.1" if host == "testclient" else host)

        monkeypatch.setattr("kavach.api.security.ipaddress.ip_address", testclient_loopback)

        response = client.get("/api/v1/hardware/provider")
        assert response.status_code == 200
        data = response.json()

        assert "requested" in data
        assert "actual" in data
        assert "is_fallback" in data
        assert "fallback_reason" in data

        # Should be CPU by default
        assert data["actual"] == "cpu"
