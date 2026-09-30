"""API route handlers."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.responses import Response

from kavach import __version__
from kavach.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BenchmarkRequest,
    BenchmarkResponse,
    HardwareCapabilitiesResponse,
    HealthResponse,
    IngestResponse,
    ProviderStatusResponse,
    RedactRequest,
    RedactResponse,
    RestoreRequest,
    RestoreResponse,
    TokenReplacement,
)
from kavach.core.pipeline import analyze_candidates, analyze_text
from kavach.core.redaction import InvalidApprovalError, redact_approved
from kavach.core.restoration import restore_tokens
from kavach.core.session_store import SessionLimitError, SessionNotFoundError, SessionStore
from kavach.detectors.contextual import get_contextual_detector
from kavach.hardware.benchmark import run_detection_benchmark
from kavach.hardware.capabilities import get_capabilities
from kavach.hardware.providers import get_provider_selection
from kavach.ingest.image_ocr import get_ocr_instance
from kavach.ingest.pdf_text import get_pdf_extractor
from kavach.ingest.service import (
    IngestError,
    preprocess_image,
    validate_file_upload,
    validate_image_constraints,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    try:
        ocr_provider = get_ocr_instance().provider
    except Exception:
        ocr_provider = "unavailable"

    contextual = get_contextual_detector()

    return HealthResponse(
        version=__version__,
        ocr_provider=ocr_provider,
        contextual_model_available=contextual.available,
        contextual_model_status=contextual.status,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request_body: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze text for PII candidates."""
    candidates = analyze_text(request_body.text)
    return AnalyzeResponse(candidates=candidates)


@router.post("/redact", response_model=RedactResponse)
async def redact(request_body: RedactRequest, request: Request) -> RedactResponse:
    """Redact only the detection candidates explicitly approved by the user."""
    candidates = analyze_candidates(request_body.text)
    try:
        result = redact_approved(
            request_body.text, candidates, request_body.approved_candidate_ids
        )
    except InvalidApprovalError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_approval", "message": str(exc)},
        ) from exc

    store: SessionStore = request.app.state.session_store
    try:
        session_id = store.create(result.token_map)
    except SessionLimitError as exc:
        raise HTTPException(
            status_code=413,
            detail={"error": "session_too_large", "message": str(exc)},
        ) from exc

    return RedactResponse(
        session_id=session_id,
        redacted_text=result.redacted_text,
        replacements=[
            TokenReplacement(token=item.token, category=item.category, count=item.count)
            for item in result.replacements
        ],
    )


@router.post("/restore", response_model=RestoreResponse)
async def restore(request_body: RestoreRequest, request: Request) -> RestoreResponse:
    """Restore known Kavach placeholders from a live local session."""
    store: SessionStore = request.app.state.session_store
    try:
        token_map = store.get(request_body.session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found", "message": "Session is missing or expired"},
        ) from exc

    result = restore_tokens(request_body.text, token_map)
    return RestoreResponse(
        restored_text=result.restored_text,
        restored_count=result.restored_count,
        unresolved_tokens=result.unresolved_tokens,
    )


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request) -> Response:
    """Delete a token map immediately; deleting a missing session is harmless."""
    store: SessionStore = request.app.state.session_store
    store.delete(session_id)
    return Response(status_code=204)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(file: Annotated[UploadFile, File()]) -> IngestResponse:
    """Ingest image or PDF file and extract text for review."""
    try:
        # Read file content
        file_content = await file.read()

        # Validate file
        mime_type, content_type = validate_file_upload(file_content, file.filename or "")

        # Extract text based on content type
        if content_type == "image":
            # Validate and preprocess image
            image = validate_image_constraints(file_content)
            image = preprocess_image(image)

            # Extract text using OCR
            ocr = get_ocr_instance()
            extracted_text, metadata = ocr.extract_text(image)

        elif content_type == "pdf":
            # Extract text from PDF
            pdf_extractor = get_pdf_extractor()
            extracted_text, metadata = pdf_extractor.extract_text(file_content)

        else:
            raise IngestError(f"Unsupported content type: {content_type}")

        # Analyze extracted text for PII candidates
        candidates = analyze_text(extracted_text) if extracted_text.strip() else []

        return IngestResponse(
            extracted_text=extracted_text,
            metadata=metadata,
            candidates=candidates
        )

    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ingestion failed") from e
    finally:
        await file.close()


@router.get("/hardware/capabilities", response_model=HardwareCapabilitiesResponse)
async def get_hardware_capabilities() -> HardwareCapabilitiesResponse:
    """Get detected hardware capabilities."""
    caps = get_capabilities()
    return HardwareCapabilitiesResponse(
        architecture=caps.architecture,
        platform_name=caps.platform_name,
        cpu_available=caps.cpu_available,
        amd_npu_available=caps.amd_npu_available,
        amd_npu_reason=caps.amd_npu_reason,
        snapdragon_available=caps.snapdragon_available,
        snapdragon_reason=caps.snapdragon_reason,
    )


@router.get("/hardware/provider", response_model=ProviderStatusResponse)
async def get_provider_status() -> ProviderStatusResponse:
    """Get current provider selection status."""
    provider = get_provider_selection()
    return ProviderStatusResponse(
        requested=provider.requested.value,
        actual=provider.actual.value,
        is_fallback=provider.is_fallback,
        fallback_reason=provider.fallback_reason,
    )


@router.post("/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(request_body: BenchmarkRequest) -> BenchmarkResponse:
    """Run bounded synthetic detection benchmark.

    WARNING: This runs actual detection workload. Do not send real PII.
    """
    result = run_detection_benchmark(repetitions=request_body.repetitions)

    return BenchmarkResponse(
        method=result.method,
        workload_description=result.workload_description,
        repetitions=result.repetitions,
        provider=result.provider,
        runtime=result.runtime,
        device_label=result.device_label,
        elapsed_seconds=result.elapsed_seconds,
        throughput_items_per_sec=result.throughput_items_per_sec,
    )
