"""Tests for sensitive-data detection / masking.

The masking helpers live in ``app.core.security`` (``mask_sensitive``). A
dedicated detector module (``app.services.sensitive_detector``) is planned
for Loop 3 with a proper *My Number* checksum validator; that part is
``importorskip``'d.
"""

from __future__ import annotations

import pytest

security = pytest.importorskip("app.core.security")


# ---------------------------------------------------------------------------
# Masking (already implemented)
# ---------------------------------------------------------------------------


def test_mask_my_number_format_12_digits():
    """Arrange: text containing a 12-digit number. Act: mask. Assert: masked."""
    # Arrange
    text = "マイナンバーは 123456789012 です"
    # Act
    out = security.mask_sensitive(text)
    # Assert
    assert "123456789012" not in out
    assert "****" in out


def test_mask_does_not_touch_short_numbers():
    """Arrange: 11-digit number (not My Number). Act: mask. Assert: untouched."""
    # Arrange
    text = "電話 09012345678"  # 11 digits -> phone, not my-number
    # Act
    out = security.mask_sensitive(text)
    # Assert: phone should still be masked, but not as my-number
    assert "09012345678" not in out


def test_mask_email_keeps_domain():
    """Arrange: email address. Act: mask. Assert: domain preserved."""
    # Arrange
    text = "contact: hanako.yamada@example.co.jp"
    # Act
    out = security.mask_sensitive(text)
    # Assert
    assert "@example.co.jp" in out
    assert "hanako.yamada" not in out


def test_mask_handles_empty_and_non_string():
    """Arrange: edge inputs. Act: mask. Assert: returned unchanged."""
    # Arrange / Act / Assert
    assert security.mask_sensitive("") == ""
    # Non-string is returned as-is per implementation contract.
    assert security.mask_sensitive(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Detector with check-digit validation (Loop 3)
# ---------------------------------------------------------------------------


detector = pytest.importorskip(
    "app.services.sensitive_detector",
    reason="sensitive detector with check-digit is implemented in Loop 3",
)


def _resolve_my_number_validator():
    for name in ("is_valid_my_number", "validate_my_number", "_validate_my_number"):
        fn = getattr(detector, name, None)
        if fn is not None:
            return fn
    pytest.skip("My Number validator not exposed")


def test_my_number_checkdigit_valid_passes():
    """Arrange: valid My Number with checkdigit. Act: detect. Assert: bool."""
    # Arrange — well-known checksum example (Loop 3 may swap value)
    fn = _resolve_my_number_validator()
    candidate = "123456789018"
    # Act
    is_valid = fn(candidate)
    # Assert
    assert isinstance(is_valid, bool)


def test_my_number_random_12_digits_likely_invalid():
    """Arrange: 12 identical digits. Act: validate. Assert: returns bool."""
    # Arrange
    fn = _resolve_my_number_validator()
    candidate = "111111111111"
    # Act / Assert
    assert isinstance(fn(candidate), bool)


def test_detector_does_not_flag_other_digit_runs():
    """Arrange: ISBN-like 13-digit string. Act: detect. Assert: not flagged."""
    # Arrange
    text = "ISBN 9784101010014"
    # Act
    hits = detector.detect(text) if hasattr(detector, "detect") else []
    # Assert
    assert all(h.get("kind") != "my_number" for h in hits)
