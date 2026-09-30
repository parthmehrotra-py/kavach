"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, ConfigDict, Field

from kavach.config import settings


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str = "ok"
    version: str
    ocr_provider: str
    contextual_model_available: bool
    contextual_model_status: str  # 'available', 'unavailable', or error reason


class DetectionCandidate(BaseModel):
    """A candidate PII detection."""

    id: str
    category: str
    start: int
    end: int
    value_preview: str  # Masked by default
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # Which detector found this
    validator_status: str | None = None


class AnalyzeRequest(BaseModel):
    """Request to analyze text for PII."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=settings.max_text_length)


class AnalyzeResponse(BaseModel):
    """Response from analyze endpoint."""

    candidates: list[DetectionCandidate]


class RedactRequest(BaseModel):
    """Source text and user-approved detection IDs."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=settings.max_text_length)
    approved_candidate_ids: list[str] = Field(min_length=1, max_length=1000)


class TokenReplacement(BaseModel):
    """Non-sensitive summary of a placeholder replacement."""

    token: str
    category: str
    count: int = Field(ge=1)


class RedactResponse(BaseModel):
    session_id: str
    redacted_text: str
    replacements: list[TokenReplacement]


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=20, max_length=128)
    text: str = Field(max_length=settings.max_text_length)


class RestoreResponse(BaseModel):
    restored_text: str
    restored_count: int = Field(ge=0)
    unresolved_tokens: list[str]


class IngestResponse(BaseModel):
    """Response from ingest endpoint."""

    extracted_text: str
    metadata: dict
    candidates: list[DetectionCandidate]


class HardwareCapabilitiesResponse(BaseModel):
    """Hardware capabilities report."""

    architecture: str
    platform_name: str
    cpu_available: bool
    amd_npu_available: bool
    amd_npu_reason: str
    snapdragon_available: bool
    snapdragon_reason: str


class ProviderStatusResponse(BaseModel):
    """Current provider selection status."""

    requested: str
    actual: str
    is_fallback: bool
    fallback_reason: str | None


class BenchmarkRequest(BaseModel):
    """Request to run benchmark."""

    model_config = ConfigDict(extra="forbid")

    repetitions: int = Field(default=10, ge=1, le=100)


class BenchmarkResponse(BaseModel):
    """Benchmark result with measured timings."""

    method: str
    workload_description: str
    repetitions: int
    provider: str
    runtime: str
    device_label: str
    elapsed_seconds: float
    throughput_items_per_sec: float | None
