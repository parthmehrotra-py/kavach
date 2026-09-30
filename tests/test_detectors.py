"""Test PII detectors."""


from kavach.detectors.aadhaar import AadhaarDetector, validate_verhoeff_checksum
from kavach.detectors.account import AccountDetector
from kavach.detectors.pan import PANDetector
from kavach.detectors.phone import PhoneDetector


class TestAadhaarDetector:
    """Test Aadhaar detection and validation."""

    def test_verhoeff_validation_standard_vectors(self):
        """Test Verhoeff checksum with known valid/invalid examples."""
        # Known valid Aadhaar checksums (synthetic)
        assert validate_verhoeff_checksum("123456789012") is False  # Invalid
        assert validate_verhoeff_checksum("234567890009") is True   # Valid synthetic

        # Edge cases
        assert validate_verhoeff_checksum("") is False
        assert validate_verhoeff_checksum("12345") is False  # Too short
        assert validate_verhoeff_checksum("1234567890123") is False  # Too long
        assert validate_verhoeff_checksum("abcd56789012") is False  # Non-digits

    def test_aadhaar_detection_formatted(self):
        """Test Aadhaar detection with various formats."""
        detector = AadhaarDetector()

        # Valid formatted Aadhaar (synthetic with valid checksum)
        text = "My Aadhaar is 2345-6789-0009 and my phone is 9876543210"
        spans = detector.detect(text)

        # Should find the valid Aadhaar
        aadhaar_spans = [s for s in spans if s.category == "aadhaar"]
        assert len(aadhaar_spans) == 1
        assert aadhaar_spans[0].value == "2345-6789-0009"
        assert aadhaar_spans[0].validator_status == "valid_checksum"

    def test_aadhaar_rejects_invalid_patterns(self):
        """Test Aadhaar detector rejects invalid patterns."""
        detector = AadhaarDetector()

        # Invalid patterns that should be rejected
        invalid_cases = [
            "0123456789012",  # Starts with 0
            "1123456789012",  # Starts with 1
            "123456789013",   # Invalid checksum
        ]

        for invalid in invalid_cases:
            spans = detector.detect(f"Number: {invalid}")
            aadhaar_spans = [s for s in spans if s.category == "aadhaar"]
            assert len(aadhaar_spans) == 0, f"Should reject {invalid}"


class TestPANDetector:
    """Test PAN detection."""

    def test_pan_valid_format(self):
        """Test PAN detection with valid format."""
        detector = PANDetector()

        text = "My PAN is ABCDE1234F and account number is 1234567890"
        spans = detector.detect(text)

        pan_spans = [s for s in spans if s.category == "pan"]
        assert len(pan_spans) == 1
        assert pan_spans[0].value == "ABCDE1234F"
        assert pan_spans[0].validator_status == "format_valid"

    def test_pan_invalid_format(self):
        """Test PAN detector rejects invalid formats."""
        detector = PANDetector()

        invalid_cases = [
            "ABCDE12345",     # Too many digits
            "ABCD1234F",      # Too few letters
            "abcde1234f",     # Lowercase
            "ABCDE1234FF",    # Too many letters at end
        ]

        for invalid in invalid_cases:
            spans = detector.detect(f"PAN: {invalid}")
            pan_spans = [s for s in spans if s.category == "pan"]
            assert len(pan_spans) == 0, f"Should reject {invalid}"


class TestPhoneDetector:
    """Test phone number detection."""

    def test_phone_indian_formats(self):
        """Test Indian phone number formats."""
        detector = PhoneDetector()

        text = "Call me at +91 9876543210 or 8765432109"
        spans = detector.detect(text)

        phone_spans = [s for s in spans if s.category == "phone"]
        assert len(phone_spans) == 2

        # +91 format should have higher confidence
        intl_phone = next(s for s in phone_spans if "+91" in s.value)
        assert intl_phone.confidence == 0.8

        local_phone = next(s for s in phone_spans if "+91" not in s.value)
        assert local_phone.confidence == 0.7

    def test_phone_rejects_invalid_patterns(self):
        """Test phone detector rejects invalid patterns."""
        detector = PhoneDetector()

        invalid_cases = [
            "1234567890",  # Doesn't start with 6-9
            "567890123",   # Too short
            "98765432101", # Too long
        ]

        for invalid in invalid_cases:
            spans = detector.detect(f"Phone: {invalid}")
            phone_spans = [s for s in spans if s.category == "phone"]
            assert len(phone_spans) == 0, f"Should reject {invalid}"


def test_phone_number_context_does_not_create_account_candidate():
    """Generic word 'number' must not be enough to infer a bank account."""
    spans = AccountDetector().detect("Phone number: 9876543210")

    assert spans == []


def test_account_detector_requires_account_specific_context():
    """Account-specific context remains sufficient for candidate detection."""
    spans = AccountDetector().detect("Bank account: 123456789012")

    assert len(spans) == 1
    assert spans[0].category == "account"
