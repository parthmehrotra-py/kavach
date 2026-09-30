"""Test candidate merging and overlap resolution."""


from kavach.core.merge import assign_stable_ids, resolve_overlaps
from kavach.core.models import Candidate


def test_resolve_overlaps_no_overlap():
    """Test non-overlapping candidates are preserved."""
    candidates = [
        Candidate("1", 0, 5, "12345", "test", 0.8, "detector1"),
        Candidate("2", 10, 15, "67890", "test", 0.7, "detector2"),
    ]

    resolved = resolve_overlaps(candidates)

    assert len(resolved) == 2
    assert resolved[0].start == 0
    assert resolved[1].start == 10


def test_resolve_overlaps_higher_confidence_wins():
    """Test higher confidence candidate wins overlap."""
    candidates = [
        Candidate("1", 0, 5, "12345", "test", 0.7, "detector1"),
        Candidate("2", 2, 7, "34567", "test", 0.9, "detector2"),  # Higher confidence
    ]

    resolved = resolve_overlaps(candidates)

    assert len(resolved) == 1
    assert resolved[0].id == "2"
    assert resolved[0].confidence == 0.9


def test_resolve_overlaps_longer_span_wins():
    """Test longer span wins when confidence is equal."""
    candidates = [
        Candidate("1", 0, 5, "12345", "test", 0.8, "detector1"),    # Length 5
        Candidate("2", 2, 9, "3456789", "test", 0.8, "detector2"),  # Length 7
    ]

    resolved = resolve_overlaps(candidates)

    assert len(resolved) == 1
    assert resolved[0].id == "2"
    assert len(resolved[0].value) == 7


def test_resolve_overlaps_stable_detector_tiebreak():
    """Test stable detector ID breaks ties."""
    candidates = [
        Candidate("1", 0, 5, "12345", "test", 0.8, "detector_z"),  # Later alphabetically
        Candidate("2", 2, 7, "34567", "test", 0.8, "detector_a"),  # Earlier alphabetically
    ]

    resolved = resolve_overlaps(candidates)

    assert len(resolved) == 1
    assert resolved[0].source == "detector_a"  # Earlier wins


def test_lower_priority_bridge_does_not_remove_independent_candidates():
    """Keep two disjoint strong spans when a weaker span bridges their gap."""
    candidates = [
        Candidate("left", 0, 6, "123456", "left", 0.95, "left_detector"),
        Candidate("bridge", 4, 12, "56789012", "bridge", 0.7, "bridge_detector"),
        Candidate("right", 10, 16, "123456", "right", 0.9, "right_detector"),
    ]

    resolved = resolve_overlaps(candidates)

    assert [candidate.id for candidate in resolved] == ["left", "right"]


def test_assign_stable_ids():
    """Test stable ID assignment by category."""
    candidates = [
        Candidate("temp1", 5, 10, "67890", "phone", 0.8, "detector1"),
        Candidate("temp2", 0, 5, "12345", "aadhaar", 0.9, "detector2"),
        Candidate("temp3", 15, 20, "ABCDE", "pan", 0.7, "detector3"),
        Candidate("temp4", 25, 30, "99999", "phone", 0.6, "detector1"),
    ]

    result = assign_stable_ids(candidates)

    # Should be ordered by position
    assert result[0].category == "aadhaar"
    assert result[0].id == "aadhaar_000"

    assert result[1].category == "phone"
    assert result[1].id == "phone_000"

    assert result[2].category == "pan"
    assert result[2].id == "pan_000"

    assert result[3].category == "phone"
    assert result[3].id == "phone_001"


def test_stable_ids_same_input_same_output():
    """Test that same input produces same IDs."""
    candidates = [
        Candidate("temp1", 0, 5, "12345", "test", 0.8, "detector1"),
        Candidate("temp2", 10, 15, "67890", "test", 0.7, "detector2"),
    ]

    result1 = assign_stable_ids(candidates.copy())
    result2 = assign_stable_ids(candidates.copy())

    assert result1[0].id == result2[0].id
    assert result1[1].id == result2[1].id
