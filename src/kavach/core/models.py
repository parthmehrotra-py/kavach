"""Internal models for candidate processing."""

from dataclasses import dataclass
from uuid import uuid4

from kavach.detectors.base import DetectionSpan


@dataclass
class Candidate:
    """Internal representation of a PII candidate."""

    id: str
    start: int
    end: int
    value: str
    category: str
    confidence: float
    source: str
    validator_status: str | None = None

    @classmethod
    def from_detection_span(cls, span: DetectionSpan, candidate_id: str | None = None) -> "Candidate":
        """Create candidate from detection span."""
        return cls(
            id=candidate_id or str(uuid4()),
            start=span.start,
            end=span.end,
            value=span.value,
            category=span.category,
            confidence=span.confidence,
            source=span.source,
            validator_status=span.validator_status,
        )

    def get_preview(self, reveal: bool = False) -> str:
        """Get masked or full value preview."""
        if reveal:
            return self.value

        # Mask most characters, show first/last for context
        if len(self.value) <= 4:
            return "*" * len(self.value)
        return self.value[:2] + "*" * (len(self.value) - 4) + self.value[-2:]
