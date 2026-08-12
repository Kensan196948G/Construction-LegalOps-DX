"""契約種別マスタ統合の単体テスト（エイリアス正規化）."""

from __future__ import annotations

import pytest

from app.services.contract_type import (
    CANONICAL_CONTRACT_TYPES,
    normalize_contract_type,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ukeoi", "工事請負契約"),
        ("itaku", "業務委託契約"),
        ("請負", "工事請負契約"),
        ("委託", "業務委託契約"),
        ("賃借", "賃貸借契約"),
        ("秘密保持", "秘密保持契約"),
        ("工事請負", "工事請負契約"),
        ("業務委託", "業務委託契約"),
        ("資材購入", "資材購入契約"),
        ("設計監理", "設計監理契約"),
    ],
)
def test_normalize_legacy_aliases(raw: str, expected: str) -> None:
    assert normalize_contract_type(raw) == expected


def test_normalize_canonical_value_is_identity() -> None:
    for value in CANONICAL_CONTRACT_TYPES:
        assert normalize_contract_type(value) == value


def test_normalize_unknown_custom_type_passes_through() -> None:
    assert normalize_contract_type("特別監理契約") == "特別監理契約"


def test_normalize_none_returns_none() -> None:
    assert normalize_contract_type(None) is None
