"""Sensitive-information detector.

Detects PII and other confidential tokens (My Number, phone, email, bank
account numbers, anti-social keywords, bribery-related keywords) in free
text. Used by :mod:`app.services.ai_review` as a pre-processing step
before sending text to the external LLM, in compliance with
``docs/ai_disclaimer_policy.md`` section 5 (masking rules).

The implementation is intentionally regex/keyword-driven (deterministic,
auditable) — heavier NER models are out of scope for Loop 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class DetectionCategory(str, Enum):
    """Category of a sensitive-token detection."""

    MY_NUMBER = "my_number"
    PHONE = "phone"
    EMAIL = "email"
    BANK_ACCOUNT = "bank_account"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    ANTISOCIAL_KEYWORD = "antisocial_keyword"
    BRIBERY_KEYWORD = "bribery_keyword"
    CREDIT_CARD = "credit_card"


@dataclass(frozen=True, slots=True)
class Detection:
    """A single sensitive-token detection result."""

    category: DetectionCategory
    value: str
    start: int
    end: int
    confidence: float = 1.0
    notes: str | None = None


# --- Regex patterns -------------------------------------------------------

# Japanese My Number: 12 consecutive digits, possibly separated by spaces/hyphens
# Validated via check-digit algorithm before reporting.
_MY_NUMBER_PATTERN: Final = re.compile(r"(?<!\d)(\d[\s\-]?){11}\d(?!\d)")

# Phone numbers: Japanese fixed-line / mobile / IP-phone (loose match).
_PHONE_PATTERN: Final = re.compile(
    r"(?<!\d)(?:0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4})(?!\d)"
)

_EMAIL_PATTERN: Final = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
)

# Bank account hint: 7-digit account numbers after kana for 普通/当座 etc.
_BANK_ACCOUNT_PATTERN: Final = re.compile(
    r"(?:普通|当座|貯蓄)[^\d]{0,8}(\d{7})"
)

# Passport number: 1 letter + 8 alphanumeric (current Japanese passport format).
_PASSPORT_PATTERN: Final = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![A-Za-z0-9])")

# Driver license: 12-digit number commonly written contiguously.
_DRIVER_LICENSE_PATTERN: Final = re.compile(r"(?<!\d)\d{12}(?!\d)")

# Credit card (loose): 13-19 digits possibly separated by hyphens/spaces.
_CREDIT_CARD_PATTERN: Final = re.compile(
    r"(?<!\d)(?:\d[\s\-]?){12,18}\d(?!\d)"
)

# --- Keyword lists --------------------------------------------------------

# Simplified anti-social-forces keyword list. The real production list is
# maintained by 法務 DX チーム; this file holds the dev/test seed.
_ANTISOCIAL_KEYWORDS: Final[tuple[str, ...]] = (
    "暴力団",
    "暴力団員",
    "暴力団関係者",
    "総会屋",
    "特殊知能暴力集団",
    "反社会的勢力",
    "反社",
    "みかじめ料",
    "フロント企業",
    "共生者",
)

# Bribery / FCPA / Bribery Act / 贈収賄 simple keyword seeds.
_BRIBERY_KEYWORDS: Final[tuple[str, ...]] = (
    "贈賄",
    "収賄",
    "贈収賄",
    "賄賂",
    "リベート",
    "キックバック",
    "袖の下",
    "便宜供与",
    "FCPA",
    "Bribery Act",
    "Foreign Corrupt Practices",
    "facilitation payment",
)


def _validate_my_number(digits: str) -> bool:
    """Return ``True`` when ``digits`` (length 12) passes the My Number
    check-digit algorithm defined by 総務省告示.
    """
    if len(digits) != 12 or not digits.isdigit():
        return False
    weights = (6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(digits[:11], weights, strict=True))
    remainder = total % 11
    check = 0 if remainder <= 1 else 11 - remainder
    return check == int(digits[11])


def _luhn(digits: str) -> bool:
    """Luhn check for credit-card number candidates."""
    if not digits.isdigit():
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        n = int(ch)
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass(slots=True)
class SensitiveDetector:
    """Stateless detector exposed as a class for DI / mocking."""

    antisocial_keywords: tuple[str, ...] = field(default=_ANTISOCIAL_KEYWORDS)
    bribery_keywords: tuple[str, ...] = field(default=_BRIBERY_KEYWORDS)

    def detect(self, text: str) -> list[Detection]:
        """Return all detections found in ``text``.

        Detections are returned in the order they appear in the input.
        """
        if not text:
            return []
        results: list[Detection] = []

        # My Number (with check digit validation)
        for m in _MY_NUMBER_PATTERN.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if _validate_my_number(digits):
                results.append(
                    Detection(
                        category=DetectionCategory.MY_NUMBER,
                        value=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        confidence=1.0,
                    )
                )

        # Phone
        for m in _PHONE_PATTERN.finditer(text):
            results.append(
                Detection(
                    category=DetectionCategory.PHONE,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.7,
                )
            )

        # Email
        for m in _EMAIL_PATTERN.finditer(text):
            results.append(
                Detection(
                    category=DetectionCategory.EMAIL,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                )
            )

        # Bank account
        for m in _BANK_ACCOUNT_PATTERN.finditer(text):
            results.append(
                Detection(
                    category=DetectionCategory.BANK_ACCOUNT,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.8,
                )
            )

        # Passport
        for m in _PASSPORT_PATTERN.finditer(text):
            results.append(
                Detection(
                    category=DetectionCategory.PASSPORT,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.6,
                )
            )

        # Driver license (loose: do not over-fire when overlapping with
        # validated My Number — filter those out).
        my_number_ranges = [
            (d.start, d.end)
            for d in results
            if d.category == DetectionCategory.MY_NUMBER
        ]
        for m in _DRIVER_LICENSE_PATTERN.finditer(text):
            if any(s <= m.start() < e for s, e in my_number_ranges):
                continue
            results.append(
                Detection(
                    category=DetectionCategory.DRIVER_LICENSE,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.4,
                    notes="loose 12-digit match; verify manually",
                )
            )

        # Credit card (Luhn-validated)
        for m in _CREDIT_CARD_PATTERN.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits):
                results.append(
                    Detection(
                        category=DetectionCategory.CREDIT_CARD,
                        value=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        confidence=0.9,
                    )
                )

        # Keywords
        for kw in self.antisocial_keywords:
            for m in re.finditer(re.escape(kw), text, flags=re.IGNORECASE):
                results.append(
                    Detection(
                        category=DetectionCategory.ANTISOCIAL_KEYWORD,
                        value=m.group(0),
                        start=m.start(),
                        end=m.end(),
                    )
                )
        for kw in self.bribery_keywords:
            for m in re.finditer(re.escape(kw), text, flags=re.IGNORECASE):
                results.append(
                    Detection(
                        category=DetectionCategory.BRIBERY_KEYWORD,
                        value=m.group(0),
                        start=m.start(),
                        end=m.end(),
                    )
                )

        results.sort(key=lambda d: (d.start, d.category.value))
        return results

    def mask(self, text: str, detections: list[Detection] | None = None) -> str:
        """Return ``text`` with all detected spans replaced by category tokens.

        Spans are processed right-to-left to keep indices stable.
        """
        if detections is None:
            detections = self.detect(text)
        if not detections:
            return text
        # Resolve overlaps: prefer earliest-start, longest-span.
        sorted_dets = sorted(detections, key=lambda d: (d.start, -(d.end - d.start)))
        non_overlap: list[Detection] = []
        cursor = -1
        for d in sorted_dets:
            if d.start >= cursor:
                non_overlap.append(d)
                cursor = d.end
        # Apply right-to-left.
        out = text
        for d in reversed(non_overlap):
            token = f"<{d.category.value.upper()}>"
            out = out[: d.start] + token + out[d.end :]
        return out


def detect(text: str) -> list[Detection]:
    """Module-level convenience wrapper for the default detector."""
    return SensitiveDetector().detect(text)


def mask(text: str) -> str:
    """Module-level convenience wrapper that masks all detections."""
    return SensitiveDetector().mask(text)
