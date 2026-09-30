"""Replace user-approved detection spans with collision-safe placeholders."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass

from kavach.core.models import Candidate


@dataclass(frozen=True)
class Replacement:
    token: str
    category: str
    count: int


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    token_map: dict[str, str]
    replacements: list[Replacement]


class InvalidApprovalError(ValueError):
    """Raised when approved candidate IDs do not match the current input."""


def redact_approved(
    text: str, candidates: list[Candidate], approved_candidate_ids: list[str]
) -> RedactionResult:
    by_id = {candidate.id: candidate for candidate in candidates}
    if len(set(approved_candidate_ids)) != len(approved_candidate_ids):
        raise InvalidApprovalError("Approved candidate IDs must be unique")
    if any(candidate_id not in by_id for candidate_id in approved_candidate_ids):
        raise InvalidApprovalError("One or more approved candidate IDs are invalid")

    approved = sorted(
        (by_id[candidate_id] for candidate_id in approved_candidate_ids),
        key=lambda candidate: (candidate.start, candidate.end),
    )
    previous_end = -1
    for candidate in approved:
        if (
            candidate.start < previous_end
            or candidate.start < 0
            or candidate.end > len(text)
            or candidate.start >= candidate.end
            or text[candidate.start : candidate.end] != candidate.value
        ):
            raise InvalidApprovalError("Approved spans no longer match the source text")
        previous_end = candidate.end

    value_tokens: dict[str, str] = {}
    token_map: dict[str, str] = {}
    replacement_counts: OrderedDict[str, tuple[str, int]] = OrderedDict()
    category_counts: dict[str, int] = {}
    spans: list[tuple[int, int, str]] = []

    for candidate in approved:
        token = value_tokens.get(candidate.value)
        if token is None:
            category = re.sub(r"[^A-Z0-9_]", "", candidate.category.upper()) or "PII"
            index = category_counts.get(category, 0) + 1
            token = f"[[KAVACH:{category}:{index:04d}]]"
            while token in text or token in token_map:
                index += 1
                token = f"[[KAVACH:{category}:{index:04d}]]"
            category_counts[category] = index
            value_tokens[candidate.value] = token
            token_map[token] = candidate.value
            replacement_counts[token] = (category, 0)

        category, count = replacement_counts[token]
        replacement_counts[token] = (category, count + 1)
        spans.append((candidate.start, candidate.end, token))

    redacted_text = text
    for start, end, token in reversed(spans):
        redacted_text = redacted_text[:start] + token + redacted_text[end:]

    replacements = [
        Replacement(token=token, category=category, count=count)
        for token, (category, count) in replacement_counts.items()
    ]
    return RedactionResult(redacted_text, token_map, replacements)
