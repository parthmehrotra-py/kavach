"""UPI ID detection."""

import re

from kavach.detectors.base import DetectionSpan


class UPIDetector:
    """UPI ID detector."""

    @property
    def name(self) -> str:
        return "upi"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect UPI IDs in text."""
        spans = []

        # UPI format: handle@provider (alphanumeric handle, @ symbol, provider domain)
        pattern = r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b'

        # Common UPI providers to increase confidence
        upi_providers = {
            'paytm', 'phonepe', 'gpay', 'amazonpay', 'mobikwik', 'freecharge',
            'ybl', 'ibl', 'axl', 'okhdfcbank', 'okicici', 'oksbi', 'okaxis'
        }

        for match in re.finditer(pattern, text):
            candidate = match.group().lower()
            provider = candidate.split('@')[1] if '@' in candidate else ''

            # Skip obvious email patterns (contains common email domains)
            if any(domain in provider for domain in ['gmail.com', 'yahoo.com', 'outlook.com']):
                continue

            confidence = 0.9 if any(p in provider for p in upi_providers) else 0.7

            spans.append(DetectionSpan(
                start=match.start(),
                end=match.end(),
                value=match.group(),
                category="upi",
                confidence=confidence,
                source=self.name,
                validator_status="format_valid"
            ))

        return spans
