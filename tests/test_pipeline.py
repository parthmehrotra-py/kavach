"""Test analysis pipeline integration."""


from kavach.core.pipeline import analyze_text


def test_analyze_text_empty():
    """Test empty text returns no candidates."""
    result = analyze_text("")
    assert result == []

    result = analyze_text("   ")  # Whitespace only
    assert result == []


def test_analyze_text_mixed_pii():
    """Test analysis with multiple PII types."""
    # Use synthetic data with valid checksums
    text = """
    Contact details:
    PAN: ABCDE1234F
    Phone: +91 9876543210
    IFSC: SBIN0001234
    UPI: user@paytm
    PIN: 560001
    """

    candidates = analyze_text(text)

    # Should detect multiple categories
    categories = {c.category for c in candidates}
    expected_categories = {"pan", "phone", "ifsc", "upi", "pin"}

    assert expected_categories.issubset(categories)

    # Check stable IDs
    pan_candidates = [c for c in candidates if c.category == "pan"]
    assert len(pan_candidates) == 1
    assert pan_candidates[0].id == "pan_000"

    # Check previews are masked
    for candidate in candidates:
        if len(candidate.value_preview) > 4:
            assert "*" in candidate.value_preview


def test_analyze_text_overlapping_patterns():
    """Test pipeline handles overlapping detections correctly."""
    # Create text where phone and account patterns might overlap
    text = "Account number 9876543210123456 and phone 9876543210"

    candidates = analyze_text(text)

    # Should resolve overlaps deterministically
    positions = [(c.start, c.end) for c in candidates]

    # No overlapping positions should remain
    for i, (start1, end1) in enumerate(positions):
        for j, (start2, end2) in enumerate(positions[i+1:], i+1):
            assert not (start1 < end2 and end1 > start2), \
                f"Overlap found: {positions[i]} and {positions[j]}"


def test_analyze_text_confidence_ordering():
    """Test candidates maintain confidence information."""
    text = "PAN ABCDE1234F and phone +91 9876543210"

    candidates = analyze_text(text)

    # All should have reasonable confidence values
    for candidate in candidates:
        assert 0.0 <= candidate.confidence <= 1.0
        assert candidate.source in ["aadhaar", "pan", "ifsc", "upi", "phone", "pin", "account"]
