"""Base detector protocol."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class DetectionSpan:
    """A detected sensitive span."""

    start: int
    end: int
    value: str
    category: str
    confidence: float
    source: str
    validator_status: str | None = None


class Detector(Protocol):
    """Protocol for PII detectors."""

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect PII spans in text."""
        ...

    @property
    def name(self) -> str:
        """Detector name for attribution."""
        ...
