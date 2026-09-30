"""Focused tests for exact, approval-based replacement and restoration."""

from kavach.core.models import Candidate
from kavach.core.redaction import InvalidApprovalError, redact_approved
from kavach.core.restoration import restore_tokens


def _candidate(candidate_id: str, text: str, start: int, category: str = "pan") -> Candidate:
    value = text[start : start + 10]
    return Candidate(candidate_id, start, start + len(value), value, category, 0.8, category)


def test_redact_only_approved_spans_and_restore_exact_tokens():
    text = "PAN ABCDE1234F; PAN ABCDE1234F"
    first = _candidate("pan_000", text, 4)
    second = _candidate("pan_001", text, 20)

    redacted = redact_approved(text, [first, second], ["pan_000"])
    assert redacted.redacted_text == "PAN [[KAVACH:PAN:0001]]; PAN ABCDE1234F"
    assert redacted.replacements[0].count == 1

    token = redacted.replacements[0].token
    result = restore_tokens(f"Answer: {token} {token} [[KAVACH:UNKNOWN:0001]]", redacted.token_map)

    assert result.restored_text == "Answer: ABCDE1234F ABCDE1234F [[KAVACH:UNKNOWN:0001]]"
    assert result.restored_count == 2
    assert result.unresolved_tokens == ["[[KAVACH:UNKNOWN:0001]]"]


def test_repeated_approved_values_reuse_token_and_source_token_collision_is_skipped():
    value = "ABCDE1234F"
    token_collision = "[[KAVACH:PAN:0001]]"  # noqa: S105
    text = f"{token_collision} {value} {value}"
    first = _candidate("pan_000", text, len(token_collision) + 1)
    second_start = len(token_collision) + 1 + len(value) + 1
    second = _candidate("pan_001", text, second_start)

    result = redact_approved(text, [first, second], ["pan_000", "pan_001"])

    assert result.replacements[0].token != token_collision
    assert result.replacements[0].count == 2
    restored = restore_tokens(result.redacted_text, result.token_map)
    assert restored.restored_text == text
    assert restored.unresolved_tokens == [token_collision]


def test_invalid_approval_is_rejected_without_partial_redaction():
    text = "PAN ABCDE1234F"
    candidate = _candidate("pan_000", text, 4)

    try:
        redact_approved(text, [candidate], ["unknown"])
    except InvalidApprovalError:
        pass
    else:
        raise AssertionError("Unknown candidate ID should be rejected")


def test_malformed_token_does_not_hide_a_later_known_token():
    result = restore_tokens(
        "Text [[KAVACH:broken [[KAVACH:PAN:0001]]",
        {"[[KAVACH:PAN:0001]]": "ABCDE1234F"},
    )

    assert result.restored_text == "Text [[KAVACH:broken ABCDE1234F"
    assert result.restored_count == 1
    assert result.unresolved_tokens == ["[[KAVACH:broken "]
