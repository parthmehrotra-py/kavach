"""Account number detection (context-dependent)."""

import re

from kavach.detectors.base import DetectionSpan


class AccountDetector:
    """Account number detector (requires context)."""

    @property
    def name(self) -> str:
        return "account"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect account numbers in text."""
        spans = []

        # Account numbers: 8-18 digits (common bank account range)
        pattern = r'\b\d{8,18}\b'

        # Context words that suggest this is an account number
        account_context = re.compile(
            r"\b(?:account|acc|a/c)\b|\b(?:bank|savings|current|cheque|deposit)\s+account\b",
            re.IGNORECASE,
        )

        for match in re.finditer(pattern, text):
            start, end = match.span()
            candidate = match.group()

            # Skip obvious non-account patterns
            if candidate.startswith('0000') or len(set(candidate)) == 1:
                continue

            # Look for context within 30 characters before/after
            context_start = max(0, start - 30)
            context_end = min(len(text), end + 30)
            context = text[context_start:context_end]

            # Only detect with strong context
            has_context = account_context.search(context) is not None

            if has_context:
                spans.append(DetectionSpan(
                    start=start,
                    end=end,
                    value=candidate,
                    category="account",
                    confidence=0.7,  # Context-dependent, lower confidence
                    source=self.name,
                    validator_status="context_detected"
                ))

        return spans
