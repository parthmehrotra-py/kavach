"""Provider selection and management."""

import logging
from enum import Enum

from kavach.hardware.capabilities import get_capabilities

logger = logging.getLogger(__name__)


class Provider(str, Enum):
    """Available runtime providers."""

    CPU = "cpu"
    AMD_NPU = "amd-npu"
    SNAPDRAGON = "snapdragon"


class ProviderSelection:
    """Provider selection with explicit fallback."""

    def __init__(self, requested: Provider = Provider.CPU):
        """Initialize provider selection.

        Args:
            requested: Requested provider (defaults to CPU baseline)
        """
        self._requested = requested
        self._actual: Provider | None = None
        self._fallback_reason: str | None = None
        self._select_provider()

    def _select_provider(self) -> None:
        """Select provider based on capabilities and request."""
        caps = get_capabilities()

        if self._requested == Provider.CPU:
            # CPU always available
            self._actual = Provider.CPU
            self._fallback_reason = None
            logger.info("Selected provider: CPU (baseline)")

        elif self._requested == Provider.AMD_NPU:
            if caps.amd_npu_available:
                self._actual = Provider.AMD_NPU
                self._fallback_reason = None
                logger.info("Selected provider: AMD NPU")
            else:
                self._actual = Provider.CPU
                self._fallback_reason = caps.amd_npu_reason
                logger.warning(
                    f"AMD NPU requested but unavailable ({caps.amd_npu_reason}), using CPU"
                )

        elif self._requested == Provider.SNAPDRAGON:
            if caps.snapdragon_available:
                self._actual = Provider.SNAPDRAGON
                self._fallback_reason = None
                logger.info("Selected provider: Snapdragon")
            else:
                self._actual = Provider.CPU
                self._fallback_reason = caps.snapdragon_reason
                logger.warning(
                    f"Snapdragon requested but unavailable ({caps.snapdragon_reason}), using CPU"
                )

    @property
    def requested(self) -> Provider:
        """Originally requested provider."""
        return self._requested

    @property
    def actual(self) -> Provider:
        """Actually selected provider after fallback."""
        return self._actual or Provider.CPU

    @property
    def fallback_reason(self) -> str | None:
        """Reason for fallback, or None if using requested provider."""
        return self._fallback_reason

    @property
    def is_fallback(self) -> bool:
        """Whether fallback occurred."""
        return self._fallback_reason is not None


# Global provider selection (defaults to CPU)
_provider_selection: ProviderSelection | None = None


def get_provider_selection() -> ProviderSelection:
    """Get current provider selection."""
    global _provider_selection
    if _provider_selection is None:
        _provider_selection = ProviderSelection(Provider.CPU)
    return _provider_selection


def set_provider(provider: Provider) -> ProviderSelection:
    """Set requested provider (with capability-based fallback).

    Args:
        provider: Requested provider

    Returns:
        ProviderSelection with actual provider and fallback reason
    """
    global _provider_selection
    _provider_selection = ProviderSelection(provider)
    return _provider_selection
