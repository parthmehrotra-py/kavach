"""Detection pipeline orchestration."""

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Lock

from kavach.api.schemas import DetectionCandidate
from kavach.core.merge import assign_stable_ids, resolve_overlaps
from kavach.core.models import Candidate
from kavach.detectors.aadhaar import AadhaarDetector
from kavach.detectors.account import AccountDetector
from kavach.detectors.base import DetectionSpan, Detector
from kavach.detectors.contextual import get_contextual_detector
from kavach.detectors.ifsc import IFSCDetector
from kavach.detectors.pan import PANDetector
from kavach.detectors.phone import PhoneDetector
from kavach.detectors.pin import PINDetector
from kavach.detectors.upi import UPIDetector

logger = logging.getLogger(__name__)

# Initialize deterministic detectors
_DETECTORS: list[Detector] = [
    AadhaarDetector(),
    PANDetector(),
    IFSCDetector(),
    UPIDetector(),
    PhoneDetector(),
    PINDetector(),
    AccountDetector(),
]

# Thread pool for contextual detection with timeout
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="contextual")
_contextual_lock = Lock()
_contextual_future: Future[list[DetectionSpan]] | None = None


def analyze_candidates(text: str) -> list[Candidate]:
    """Return raw candidates for internal processing."""
    if not text.strip():
        return []

    # Run all deterministic detectors
    all_spans = []
    for detector in _DETECTORS:
        spans = detector.detect(text)
        all_spans.extend(spans)

    # Attempt contextual detection with timeout
    contextual = get_contextual_detector()
    if contextual.available:
        global _contextual_future
        with _contextual_lock:
            if _contextual_future is not None and not _contextual_future.done():
                future = None
            else:
                # Permit only one outstanding job; a timed-out worker may keep running.
                _contextual_future = _executor.submit(contextual.detect, text)
                future = _contextual_future

        if future is None:
            logger.debug("Contextual worker is busy; proceeding with deterministic only")
        else:
            try:
                # Run in thread pool with configured timeout
                contextual_spans = future.result(timeout=contextual.timeout_seconds)
                all_spans.extend(contextual_spans)
                logger.debug(f"Contextual detector added {len(contextual_spans)} spans")
            except FuturesTimeoutError:
                contextual.mark_degraded("timeout")
                logger.warning("Contextual detection timed out; proceeding with deterministic only")
            except Exception as e:
                contextual.mark_degraded(f"exception: {type(e).__name__}")
                logger.warning(
                    f"Contextual detection failed: {e}; proceeding with deterministic only"
                )

    # Convert to candidates
    candidates = [Candidate.from_detection_span(span) for span in all_spans]

    # Resolve overlaps and assign stable IDs
    resolved = resolve_overlaps(candidates)
    final_candidates = assign_stable_ids(resolved)

    return final_candidates


def analyze_text(text: str) -> list[DetectionCandidate]:
    """Analyze text for PII candidates and return masked API records."""
    return [
        DetectionCandidate(
            id=candidate.id,
            category=candidate.category,
            start=candidate.start,
            end=candidate.end,
            value_preview=candidate.get_preview(),
            confidence=candidate.confidence,
            source=candidate.source,
            validator_status=candidate.validator_status,
        )
        for candidate in analyze_candidates(text)
    ]
