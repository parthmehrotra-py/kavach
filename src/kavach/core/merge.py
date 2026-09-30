"""Overlap resolution and stable candidate ordering."""

from kavach.core.models import Candidate


def resolve_overlaps(candidates: list[Candidate]) -> list[Candidate]:
    """Resolve overlapping candidates with deterministic priority rules.

    Priority order:
    1. Higher confidence
    2. Longer span
    3. Stable detector ID (alphabetical)
    """
    if not candidates:
        return []

    # Consider stronger candidates first. A lower-priority span that overlaps
    # multiple independent candidates must not remove all of them.
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            -c.confidence,
            -(c.end - c.start),
            c.source,
            c.start,
            c.end,
            c.category,
            c.value,
        ),
    )
    resolved: list[Candidate] = []

    for candidate in sorted_candidates:
        if not any(
            candidate.start < existing.end and candidate.end > existing.start
            for existing in resolved
        ):
            resolved.append(candidate)

    # Final sort by start position for stable output
    return sorted(resolved, key=lambda c: c.start)


def assign_stable_ids(candidates: list[Candidate]) -> list[Candidate]:
    """Assign stable, deterministic IDs to candidates."""
    # Group by category for consistent numbering
    by_category: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        if candidate.category not in by_category:
            by_category[candidate.category] = []
        by_category[candidate.category].append(candidate)

    # Assign IDs within each category
    result = []
    for category in sorted(by_category.keys()):  # Stable category order
        category_candidates = sorted(by_category[category], key=lambda c: c.start)
        for i, candidate in enumerate(category_candidates):
            candidate.id = f"{category}_{i:03d}"
            result.append(candidate)

    # Return in position order
    return sorted(result, key=lambda c: c.start)
