"""Indian phone number detection."""

import re

from kavach.detectors.base import DetectionSpan


class PhoneDetector:
    """Indian phone number detector."""

    @property
    def name(self) -> str:
        return "phone"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect Indian phone numbers in text."""
        spans = []
        found_positions: set[tuple[int, int]] = set()

        # Indian mobile: +91 followed by 10 digits starting with 6-9
        # Various formats: +91 9999999999, +919999999999, 9999999999
        patterns = [
            (r'\+91[\s\-]?[6-9]\d{9}\b', 0.8),  # +91 format (higher confidence)
            (r'\b[6-9]\d{9}\b', 0.7),           # 10-digit format (lower confidence)
        ]

        for pattern, confidence in patterns:
            for match in re.finditer(pattern, text):
                start, end = match.span()

                # Skip if this position is already covered by a higher-confidence match
                if any(s <= start < e or s < end <= e for s, e in found_positions):
                    continue

                candidate = match.group()

                # Extract just the digits
                digits = re.sub(r'\D', '', candidate)

                # Must be exactly 10 digits for mobile (after removing country code)
                if len(digits) == 12 and digits.startswith('91'):
                    digits = digits[2:]  # Remove country code
                elif len(digits) != 10:
                    continue

                # Must start with 6-9 for Indian mobile
                if digits[0] not in '6789':
                    continue

                spans.append(DetectionSpan(
                    start=start,
                    end=end,
                    value=candidate,
                    category="phone",
                    confidence=confidence,
                    source=self.name,
                    validator_status="format_valid"
                ))
                found_positions.add((start, end))

        return spans
