"""Hardware capability detection."""

import logging
import platform
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HardwareCapabilities:
    """Detected hardware capabilities."""

    architecture: str  # AMD64, ARM64, etc.
    platform_name: str  # Windows, Linux, Darwin
    cpu_available: bool  # Always True (baseline)
    amd_npu_available: bool  # AMD NPU runtime detected
    amd_npu_reason: str  # Why AMD NPU is/isn't available
    snapdragon_available: bool  # Always False until verified on real hardware
    snapdragon_reason: str  # Always "unverified"


def detect_capabilities() -> HardwareCapabilities:
    """Detect current hardware capabilities conservatively.

    Returns:
        HardwareCapabilities with truthful detection results
    """
    arch = platform.machine()
    plat = platform.system()

    # CPU is always available (baseline requirement)
    cpu_available = True

    # AMD NPU detection (conservative)
    amd_npu_available = False
    amd_npu_reason = "not detected"

    # Architecture does not identify the CPU vendor or verify an NPU runtime.
    if arch.lower() in ("amd64", "x86_64"):
        amd_npu_reason = "x86-64 architecture detected; AMD NPU runtime not verified"
    else:
        amd_npu_reason = f"AMD NPU runtime not verified for architecture: {arch}"

    # Snapdragon/QNN always unverified until tested on real hardware
    snapdragon_available = False
    snapdragon_reason = "unverified"

    logger.info(
        f"Detected capabilities: {arch} {plat}, "
        f"CPU=available, AMD_NPU={amd_npu_available}, Snapdragon=unverified"
    )

    return HardwareCapabilities(
        architecture=arch,
        platform_name=plat,
        cpu_available=cpu_available,
        amd_npu_available=amd_npu_available,
        amd_npu_reason=amd_npu_reason,
        snapdragon_available=snapdragon_available,
        snapdragon_reason=snapdragon_reason,
    )


# Cache capabilities on first access
_capabilities: HardwareCapabilities | None = None


def get_capabilities() -> HardwareCapabilities:
    """Get cached hardware capabilities."""
    global _capabilities
    if _capabilities is None:
        _capabilities = detect_capabilities()
    return _capabilities
