"""Optional contextual NER detector using spaCy."""

import logging
from typing import Any

from kavach.detectors.base import DetectionSpan

logger = logging.getLogger(__name__)


class ContextualDetector:
    """Optional local NER detector with graceful degradation."""

    def __init__(self, model_name: str = "en_core_web_sm", timeout_seconds: float = 5.0):
        """Initialize contextual detector.

        Args:
            model_name: spaCy model name (must be installed separately)
            timeout_seconds: Maximum execution time per detection call
        """
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._nlp: Any | None = None
        self._available = False
        self._degraded = False
        self._load_error: str | None = None
        self._runtime_error: str | None = None

        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load spaCy model without raising."""
        try:
            import spacy

            self._nlp = spacy.load(self._model_name)
            self._available = True
            logger.info(f"Loaded contextual model: {self._model_name}")
        except ImportError:
            self._load_error = "spacy not installed"
            logger.info("spaCy not available; contextual detection disabled")
        except OSError:
            self._load_error = f"model '{self._model_name}' not found"
            logger.info(
                f"spaCy model '{self._model_name}' not found; "
                "run: python -m spacy download en_core_web_sm"
            )
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"Failed to load contextual model: {e}")

    @property
    def name(self) -> str:
        """Detector name for attribution."""
        return "contextual"

    @property
    def available(self) -> bool:
        """Whether the model loaded successfully."""
        return self._available

    @property
    def timeout_seconds(self) -> float:
        """Configured timeout for detection."""
        return self._timeout_seconds

    @property
    def status(self) -> str:
        """Current status: 'available', 'degraded', or error reason."""
        if self._degraded and self._runtime_error:
            return f"degraded: {self._runtime_error}"
        if self._available:
            return "available"
        return self._load_error or "unavailable"

    def mark_degraded(self, reason: str) -> None:
        """Mark detector as degraded after runtime failure."""
        self._degraded = True
        self._runtime_error = reason
        logger.warning(f"Contextual detector degraded: {reason}")

    def detect(self, text: str, max_chars: int = 5000) -> list[DetectionSpan]:
        """Detect person names and locations with bounded input.

        Args:
            text: Input text to analyze
            max_chars: Maximum text length to process (safety limit)

        Returns:
            List of detected spans, or empty list if unavailable/error
        """
        if not self._available or not self._nlp:
            return []

        if not text.strip():
            return []

        # Bound input size
        bounded_text = text[:max_chars]

        try:
            # Process with spaCy
            doc = self._nlp(bounded_text)

            spans = []
            for ent in doc.ents:
                # Map spaCy labels to Kavach categories
                category = None
                if ent.label_ == "PERSON":
                    category = "PERSON"
                elif ent.label_ in ("GPE", "LOC", "FAC"):
                    # GPE: Geopolitical entity, LOC: Location, FAC: Facility
                    category = "ADDRESS"

                if category:
                    spans.append(
                        DetectionSpan(
                            start=ent.start_char,
                            end=ent.end_char,
                            value=ent.text,
                            category=category,
                            confidence=0.7,  # Conservative for NER
                            source="contextual",
                            validator_status=None,
                        )
                    )

            return spans

        except Exception as e:
            logger.warning(f"Contextual detection failed: {e}")
            self.mark_degraded(f"exception: {type(e).__name__}")
            return []


# Global instance
_contextual_detector: ContextualDetector | None = None


def get_contextual_detector() -> ContextualDetector:
    """Get singleton contextual detector instance."""
    global _contextual_detector
    if _contextual_detector is None:
        _contextual_detector = ContextualDetector()
    return _contextual_detector


def reset_contextual_detector() -> None:
    """Reset singleton for testing."""
    global _contextual_detector
    _contextual_detector = None
