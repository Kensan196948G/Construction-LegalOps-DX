"""Extended unit tests for app.services.sensitive_detector.

Covers lines previously uncovered (73% -> 85%+):
  lines 117, 128, 154, 159-161, 173, 185, 196, 208, 226-228, 243, 256, 266,
  283-300, 310

Test categories (20 tests):
  - Individual PII detection patterns (phone, email, bank, passport, driver
    license, credit card, My Number)
  - Antisocial / bribery keyword detection
  - No-detection path (clean text / empty text)
  - SensitiveDetector.detect() multi-category simultaneous detection
  - mask() with explicit / None / empty detections
  - Module-level convenience wrappers
  - Internal helpers (_validate_my_number, _luhn)
"""

from __future__ import annotations

import pytest

we = pytest.importorskip(
    "app.services.sensitive_detector",
    reason="sensitive_detector implemented in Loop 3",
)

from app.services.sensitive_detector import (  # noqa: E402
    Detection,
    DetectionCategory,
    SensitiveDetector,
    _luhn,
    _validate_my_number,
    detect,
    mask,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detector() -> SensitiveDetector:
    return SensitiveDetector()


def _valid_my_number() -> str:
    """Return a 12-digit string that passes the My Number check-digit algorithm."""
    # '12345678901' + computed check digit (= 8)
    weights = (6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    digits = "12345678901"
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    remainder = total % 11
    check = 0 if remainder <= 1 else 11 - remainder
    return digits + str(check)  # "123456789018"


# ---------------------------------------------------------------------------
# _validate_my_number — internal helper
# ---------------------------------------------------------------------------


def test_validate_my_number_valid():
    """Arrange: correctly computed 12-digit My Number. Assert: True."""
    assert _validate_my_number(_valid_my_number()) is True


def test_validate_my_number_wrong_check_digit():
    """Arrange: valid prefix + wrong check digit. Assert: False."""
    bad = _valid_my_number()[:-1] + ("0" if _valid_my_number()[-1] != "0" else "1")
    assert _validate_my_number(bad) is False


def test_validate_my_number_non_digit():
    """Arrange: contains letters. Assert: False (line 117 branch)."""
    assert _validate_my_number("12345678901a") is False


def test_validate_my_number_wrong_length():
    """Arrange: fewer than 12 digits. Assert: False (line 117 branch)."""
    assert _validate_my_number("1234567890") is False


# ---------------------------------------------------------------------------
# _luhn — internal helper
# ---------------------------------------------------------------------------


def test_luhn_valid_visa():
    """Arrange: known-valid Visa test number. Assert: True (line 128)."""
    assert _luhn("4532015112830366") is True


def test_luhn_invalid_number():
    """Arrange: random number that fails Luhn. Assert: False (line 128)."""
    assert _luhn("1234567890123456") is False


def test_luhn_non_digit_string():
    """Arrange: contains non-digit chars. Assert: False (line 128 guard)."""
    assert _luhn("123abc") is False


# ---------------------------------------------------------------------------
# SensitiveDetector.detect — individual pattern paths
# ---------------------------------------------------------------------------


def test_detect_empty_text_returns_empty():
    """Arrange: empty string. Act: detect. Assert: empty list (line 154)."""
    assert _detector().detect("") == []


def test_detect_phone_number():
    """Arrange: Japanese phone number. Act: detect. Assert: PHONE detected (line 159-161)."""
    results = _detector().detect("電話: 03-1234-5678")
    assert any(d.category == DetectionCategory.PHONE for d in results)


def test_detect_email_address():
    """Arrange: email address. Act: detect. Assert: EMAIL detected (line 173)."""
    results = _detector().detect("連絡先: test.user@example.co.jp")
    assert any(d.category == DetectionCategory.EMAIL for d in results)
    email_det = next(d for d in results if d.category == DetectionCategory.EMAIL)
    assert email_det.confidence == 1.0


def test_detect_bank_account():
    """Arrange: text with 普通 + 7-digit account. Act: detect. Assert: BANK_ACCOUNT (line 185)."""
    results = _detector().detect("普通預金 1234567")
    assert any(d.category == DetectionCategory.BANK_ACCOUNT for d in results)
    ba_det = next(d for d in results if d.category == DetectionCategory.BANK_ACCOUNT)
    assert ba_det.confidence == 0.8


def test_detect_passport_number():
    """Arrange: Japanese passport format AB1234567. Act: detect. Assert: PASSPORT (line 196)."""
    results = _detector().detect("パスポート番号: AB1234567")
    assert any(d.category == DetectionCategory.PASSPORT for d in results)
    pp_det = next(d for d in results if d.category == DetectionCategory.PASSPORT)
    assert pp_det.confidence == 0.6


def test_detect_driver_license_12_digits():
    """Arrange: 12-digit number that is NOT a valid My Number. Act: detect.
    Assert: DRIVER_LICENSE detected (line 208 branch — not filtered by my_number_ranges).
    """
    # 123456789012 has wrong check digit for My Number (should be 8 → 18)
    results = _detector().detect("免許証: 123456789012")
    assert any(d.category == DetectionCategory.DRIVER_LICENSE for d in results)
    dl_det = next(d for d in results if d.category == DetectionCategory.DRIVER_LICENSE)
    assert dl_det.notes is not None
    assert dl_det.confidence == 0.4


def test_detect_driver_license_not_reported_when_overlaps_my_number():
    """Arrange: valid My Number. Act: detect. Assert: DRIVER_LICENSE suppressed (lines 226-228)."""
    mn = _valid_my_number()
    results = _detector().detect(f"マイナンバー: {mn}")
    categories = {d.category for d in results}
    assert DetectionCategory.MY_NUMBER in categories
    assert DetectionCategory.DRIVER_LICENSE not in categories


def test_detect_credit_card_luhn_valid():
    """Arrange: Luhn-valid card number. Act: detect. Assert: CREDIT_CARD detected (line 243)."""
    results = _detector().detect("カード番号: 4532015112830366")
    assert any(d.category == DetectionCategory.CREDIT_CARD for d in results)
    cc_det = next(d for d in results if d.category == DetectionCategory.CREDIT_CARD)
    assert cc_det.confidence == 0.9


def test_detect_antisocial_keyword():
    """Arrange: antisocial keyword. Act: detect. Assert: ANTISOCIAL_KEYWORD (line 256)."""
    results = _detector().detect("暴力団との契約は禁止")
    assert any(d.category == DetectionCategory.ANTISOCIAL_KEYWORD for d in results)


def test_detect_bribery_keyword():
    """Arrange: bribery keyword. Act: detect. Assert: BRIBERY_KEYWORD (line 266)."""
    results = _detector().detect("賄賂を受け取った疑い")
    assert any(d.category == DetectionCategory.BRIBERY_KEYWORD for d in results)


def test_detect_no_pii_returns_empty():
    """Arrange: clean text with no PII. Act: detect. Assert: empty list."""
    results = _detector().detect("本日は契約書の内容を確認します。特に問題はありません。")
    assert results == []


# ---------------------------------------------------------------------------
# SensitiveDetector.detect — multi-category simultaneous (lines 283-300)
# ---------------------------------------------------------------------------


def test_detect_multiple_categories_simultaneously():
    """Arrange: text with email AND phone. Act: detect. Assert: both detected (lines 283-300)."""
    text = "メール: foo@bar.example.com と電話: 090-9876-5432"
    results = _detector().detect(text)
    cats = {d.category for d in results}
    assert DetectionCategory.EMAIL in cats
    assert DetectionCategory.PHONE in cats


def test_detect_results_sorted_by_start():
    """Arrange: bribery keyword before antisocial in text. Assert: sorted by start index."""
    text = "賄賂と暴力団"
    results = _detector().detect(text)
    starts = [d.start for d in results]
    assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# SensitiveDetector.mask (line 310 overlap resolver)
# ---------------------------------------------------------------------------


def test_mask_auto_detects_when_detections_is_none():
    """Arrange: email in text, detections=None. Act: mask. Assert: replaced (line 310)."""
    result = _detector().mask("info@example.co.jp", detections=None)
    assert "info@example.co.jp" not in result
    assert "<EMAIL>" in result


def test_mask_empty_detections_returns_text_unchanged():
    """Arrange: email in text, detections=[]. Act: mask. Assert: unchanged."""
    text = "info@example.co.jp"
    result = _detector().mask(text, detections=[])
    assert result == text


def test_mask_multiple_spans_applied_right_to_left():
    """Arrange: text with email AND antisocial keyword. Act: mask. Assert: both replaced."""
    text = "反社 連絡先: contact@example.com"
    result = _detector().mask(text)
    assert "contact@example.com" not in result
    assert "反社" not in result


# ---------------------------------------------------------------------------
# Module-level convenience wrappers
# ---------------------------------------------------------------------------


def test_module_level_detect_function():
    """Act: call module-level detect(). Assert: returns list of Detection."""
    results = detect("反社 と 賄賂")
    assert isinstance(results, list)
    assert all(isinstance(d, Detection) for d in results)
    cats = {d.category for d in results}
    assert DetectionCategory.ANTISOCIAL_KEYWORD in cats
    assert DetectionCategory.BRIBERY_KEYWORD in cats


def test_module_level_mask_function():
    """Act: call module-level mask(). Assert: PII replaced with tokens."""
    result = mask("反社 と 賄賂")
    assert "反社" not in result
    assert "賄賂" not in result
    assert "<ANTISOCIAL_KEYWORD>" in result
    assert "<BRIBERY_KEYWORD>" in result


# ---------------------------------------------------------------------------
# Custom keyword injection
# ---------------------------------------------------------------------------


def test_custom_antisocial_keywords_detected():
    """Arrange: SensitiveDetector with custom antisocial_keywords. Assert: detected."""
    custom = SensitiveDetector(antisocial_keywords=("カスタム暴力団",), bribery_keywords=())
    results = custom.detect("カスタム暴力団が関与")
    assert any(d.category == DetectionCategory.ANTISOCIAL_KEYWORD for d in results)


def test_fcpa_bribery_keyword_detected():
    """Arrange: text containing 'FCPA' (default bribery keyword). Assert: detected."""
    results = _detector().detect("FCPA compliance review required")
    assert any(d.category == DetectionCategory.BRIBERY_KEYWORD for d in results)
