"""Aadhaar number detection and validation."""

import re

from kavach.detectors.base import DetectionSpan


def validate_verhoeff_checksum(digits: str) -> bool:
    """Validate Verhoeff checksum for Aadhaar number.

    Based on the official Verhoeff algorithm specification.
    """
    if len(digits) != 12 or not digits.isdigit():
        return False

    # Verhoeff multiplication table
    d_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]

    # Permutation table
    p_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]

    c = 0
    # Apply the Verhoeff permutation from the check digit toward the first digit.
    digits_int = [int(d) for d in reversed(digits)]

    for i in range(len(digits_int)):
        c = d_table[c][p_table[i % 8][digits_int[i]]]

    return c == 0


def normalize_aadhaar(text: str) -> str:
    """Extract and normalize Aadhaar digits from formatted text."""
    # Remove all non-digits
    return re.sub(r'\D', '', text)


class AadhaarDetector:
    """Aadhaar number detector with Verhoeff checksum validation."""

    @property
    def name(self) -> str:
        return "aadhaar"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect Aadhaar numbers in text."""
        spans = []

        # Pattern for Aadhaar: 12 digits, possibly formatted with spaces/dashes
        pattern = r'\b(?:\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b'

        for match in re.finditer(pattern, text):
            candidate = match.group()
            normalized = normalize_aadhaar(candidate)

            # Must be exactly 12 digits
            if len(normalized) != 12:
                continue

            # Reject known invalid patterns
            if normalized.startswith(('0', '1')):  # Common invalid prefixes
                continue

            # Validate Verhoeff checksum
            is_valid = validate_verhoeff_checksum(normalized)
            validator_status = "valid_checksum" if is_valid else "invalid_checksum"

            if is_valid:  # Only report valid Aadhaar numbers
                spans.append(DetectionSpan(
                    start=match.start(),
                    end=match.end(),
                    value=candidate,
                    category="aadhaar",
                    confidence=0.95,  # High confidence with valid checksum
                    source=self.name,
                    validator_status=validator_status
                ))

        return spans
