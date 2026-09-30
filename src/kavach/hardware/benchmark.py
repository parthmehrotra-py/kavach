"""Local benchmark with measured timings."""

import logging
import time
from dataclasses import dataclass

from kavach.core.pipeline import analyze_text
from kavach.detectors.contextual import get_contextual_detector
from kavach.hardware.capabilities import get_capabilities
from kavach.hardware.providers import get_provider_selection

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Measured benchmark result."""

    method: str  # What was benchmarked
    workload_description: str  # Description of synthetic workload
    repetitions: int  # Number of times workload was run
    provider: str  # Provider used (cpu, amd-npu, snapdragon)
    runtime: str  # Runtime library (e.g., "rapidocr-cpu", "spacy")
    device_label: str  # Device/architecture description
    elapsed_seconds: float  # Measured elapsed time
    throughput_items_per_sec: float | None  # Optional throughput metric


def run_detection_benchmark(
    repetitions: int = 10,
    text_samples: list[str] | None = None
) -> BenchmarkResult:
    """Benchmark PII detection pipeline on synthetic workload.

    Args:
        repetitions: Number of times to run workload
        text_samples: Synthetic text samples (if None, uses default)

    Returns:
        BenchmarkResult with measured timings and labels
    """
    if text_samples is None:
        # Default synthetic workload
        text_samples = [
            "PAN: ABCDE1234F, Phone: +91-9876543210",
            "Aadhaar: 234567890009, IFSC: SBIN0001234",
            "UPI: user@bank, Account: 1234567890123456",
        ]

    caps = get_capabilities()
    provider_sel = get_provider_selection()
    contextual_available = get_contextual_detector().available

    workload_desc = f"{len(text_samples)} synthetic text samples, {repetitions} repetitions"
    device_label = f"{caps.platform_name} {caps.architecture}"

    logger.info(f"Starting detection benchmark: {workload_desc}")

    # Measure elapsed time with monotonic clock
    start_time = time.monotonic()

    for _ in range(repetitions):
        for sample in text_samples:
            _ = analyze_text(sample)

    end_time = time.monotonic()
    elapsed = end_time - start_time

    total_items = len(text_samples) * repetitions
    throughput = total_items / elapsed if elapsed > 0 else None

    logger.info(f"Benchmark complete: {elapsed:.3f}s for {total_items} items")

    return BenchmarkResult(
        method="detection_pipeline",
        workload_description=workload_desc,
        repetitions=repetitions,
        provider=provider_sel.actual.value,
        runtime="deterministic+spacy" if contextual_available else "deterministic",
        device_label=device_label,
        elapsed_seconds=elapsed,
        throughput_items_per_sec=throughput,
    )
