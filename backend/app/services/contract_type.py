"""契約種別マスタの正準化（表記揺れ・旧名称の統合）.

2026-08-12 以前は backend テスト（``ukeoi`` / ``itaku``）・enum（``請負`` / ``委託``）・
UI（``工事請負契約`` / ``業務委託契約``）で 3 系統の値が混在していた。
正準値は ``app.models.enums.ContractType`` の UI 表示名（``工事請負契約`` 等）とし、
API 境界でエイリアスを正規化する。独自種別（正準値外）は拡張可能なまま保持する。
"""

from __future__ import annotations

from app.models.enums import ContractType

CANONICAL_CONTRACT_TYPES: tuple[str, ...] = (
    ContractType.KOUJI_UKEOI.value,
    ContractType.GYOMU_ITAKU.value,
    ContractType.SHIZAI_KOUNYUU.value,
    ContractType.SHITAKE.value,
    ContractType.SEKKEI_KANRI.value,
    ContractType.CHINSHAKU.value,
    ContractType.NDA.value,
    ContractType.BAIBAI.value,
    ContractType.OBOEGAKI.value,
    ContractType.JV.value,
    ContractType.OTHER.value,
)

_ALIASES: dict[str, str] = {
    # 旧 integration テスト等で使用された romanized コード
    "ukeoi": ContractType.KOUJI_UKEOI.value,
    "itaku": ContractType.GYOMU_ITAKU.value,
    # 旧 enum 値・旧 UI ラベル
    "請負": ContractType.KOUJI_UKEOI.value,
    "委託": ContractType.GYOMU_ITAKU.value,
    "賃借": ContractType.CHINSHAKU.value,
    "秘密保持": ContractType.NDA.value,
    "工事請負": ContractType.KOUJI_UKEOI.value,
    "業務委託": ContractType.GYOMU_ITAKU.value,
    "資材購入": ContractType.SHIZAI_KOUNYUU.value,
    "設計監理": ContractType.SEKKEI_KANRI.value,
    "売買契約書": ContractType.BAIBAI.value,
}


def normalize_contract_type(value: str | None) -> str | None:
    """エイリアスを正準値へ正規化する。未知の値はそのまま返す（カスタム種別許容）."""
    if value is None:
        return None
    normalized = value.strip()
    if normalized in CANONICAL_CONTRACT_TYPES:
        return normalized
    return _ALIASES.get(normalized, normalized)
