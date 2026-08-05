"""適用法令自動判定（決定論的ルールエンジン / 評価 AI 機能 #3）.

契約類型・資本金・従業員数・発注日・取引内容・公共/民間から
建設業法・取適法・個人情報保護法などの適用可能性を提示する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.compliance_checker import (
    _TORITEKI_MATRIX,
    TORITEKI_EFFECTIVE_DATE,
)


@dataclass(slots=True)
class ApplicableLaw:
    law_code: str
    law_name: str
    applies: bool
    confidence: float  # 0.0-1.0
    reason: str
    citation_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "law_code": self.law_code,
            "law_name": self.law_name,
            "applies": self.applies,
            "confidence": self.confidence,
            "reason": self.reason,
            "citation_url": self.citation_url,
        }


@dataclass(slots=True)
class ApplicableLawResult:
    contract_id: int | None
    contract_type: str
    laws: list[ApplicableLaw] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_type": self.contract_type,
            "laws": [law.to_dict() for law in self.laws],
            "applied": [law.to_dict() for law in self.laws if law.applies],
        }


def determine(
    *,
    contract_id: int | None = None,
    contract_type: str | None = None,
    order_date: date | None = None,
    transaction_kind: str | None = None,
    is_public_work: bool = False,
    handles_personal_data: bool = False,
    our_capital_jpy: int | None = None,
    our_employees: int | None = None,
    counterparty_capital_jpy: int | None = None,
    counterparty_employees: int | None = None,
    amount_jpy: int | None = None,
) -> ApplicableLawResult:
    """適用法令の自動判定を実行する。"""
    ct = contract_type or "その他"
    laws: list[ApplicableLaw] = []

    # 建設業法（19 条書面・24 条の 2 下請・許可要件）
    is_construction = ct in ("請負", "JV")
    laws.append(
        ApplicableLaw(
            law_code="construction_industry_act",
            law_name="建設業法",
            applies=is_construction,
            confidence=0.95 if is_construction else 0.6,
            reason=(
                "工事請負・JV 契約のため、書面交付（19 条）・下請負契約（24 条の 2）"
                "・労務費等内訳（改正 19 条）が適用されます。"
                if is_construction
                else "契約類型が請負/JV ではないため原則適用外です。"
            ),
            citation_url="https://elaws.e-gov.go.jp/document?lawid=324AC0000000100",
        )
    )

    # 取適法（旧下請法）
    toriteki_kind = transaction_kind or ("construction" if is_construction else None)
    toriteki_applies = False
    toriteki_reason = "取引類型が不明のため判定できません。"
    toriteki_conf = 0.4
    if toriteki_kind in _TORITEKI_MATRIX:
        row = _TORITEKI_MATRIX[toriteki_kind]
        cap = int(row["capital"])
        emp = int(row["employees"])
        ours_big = (our_capital_jpy or 0) > cap or (our_employees or 0) > emp
        theirs_small = (
            counterparty_capital_jpy is not None and counterparty_capital_jpy <= cap
        ) or (
            counterparty_employees is not None and counterparty_employees <= emp
        )
        if ours_big and theirs_small:
            toriteki_applies = True
            toriteki_conf = 0.85
            toriteki_reason = (
                f"取引類型「{row['label']}」で委託事業者"
                f"（資本金 {cap:,} 円超 または 従業員 {emp} 人超）"
                "かつ中小受託事業者（いずれか以下）の関係に該当します。"
            )
        elif ours_big:
            toriteki_conf = 0.6
            toriteki_reason = (
                "委託事業者側の規模は基準超ですが、"
                "相手方規模が未設定のため要確認です。"
            )
        else:
            toriteki_reason = "委託事業者側が資本金・従業員数の基準を満たしません。"
    laws.append(
        ApplicableLaw(
            law_code="toritekihou",
            law_name="中小受託取引適正化法（取適法）",
            applies=toriteki_applies,
            confidence=toriteki_conf,
            reason=toriteki_reason,
            citation_url="https://www.jftc.go.jp/partnership_package/toritekihou.html",
        )
    )

    # 公共工事: 品確法 / 入札談合等関与行為防止法
    if is_public_work:
        laws.append(
            ApplicableLaw(
                law_code="public_construction_quality_act",
                law_name="公共工事の品質確保の促進に関する法律（品確法）",
                applies=True,
                confidence=0.9,
                reason="公共工事のため、品確法の基本理念・入札契約手続が適用されます。",
            )
        )
        laws.append(
            ApplicableLaw(
                law_code="bid_rigging_prevention_act",
                law_name="入札談合等関与行為防止法",
                applies=True,
                confidence=0.85,
                reason="公共工事の発注者・受注者双方に談合関与防止の責務があります。",
            )
        )
    else:
        laws.append(
            ApplicableLaw(
                law_code="public_construction_quality_act",
                law_name="公共工事の品質確保の促進に関する法律（品確法）",
                applies=False,
                confidence=0.7,
                reason="民間工事のため原則適用外です。",
            )
        )

    # 個人情報保護法
    laws.append(
        ApplicableLaw(
            law_code="pipa",
            law_name="個人情報の保護に関する法律（個人情報保護法）",
            applies=handles_personal_data,
            confidence=0.9 if handles_personal_data else 0.5,
            reason=(
                "個人情報を取り扱うため利用目的・第三者提供・安全管理措置の規定が必要です。"
                if handles_personal_data
                else (
                    "個人情報取扱フラグが立っていないため要確認"
                    "（本文に言及がある場合は要再判定）。"
                )
            ),
            citation_url="https://www.ppc.go.jp/legal/policy/",
        )
    )

    # 電子帳簿保存法
    laws.append(
        ApplicableLaw(
            law_code="electronic_books_act",
            law_name="電子帳簿保存法",
            applies=True,
            confidence=0.7,
            reason="電子契約・電子取引を行う場合は電子データ保存要件の確認が必要です。",
        )
    )

    # 下請法→取適法の新旧切替メモ
    if toriteki_applies:
        laws.append(
            ApplicableLaw(
                law_code="law_version_switch",
                law_name="新旧法の切替（下請法 → 取適法）",
                applies=True,
                confidence=0.95,
            reason=(
                f"発注日 {order_date.isoformat() if order_date else '未設定'} の場合、"
                "2026-01-01 以降は取適法が適用されます。"
                    if order_date is not None and order_date >= TORITEKI_EFFECTIVE_DATE
                    else (
                        "発注日が 2026-01-01 より前のため旧下請法が適用されます。"
                        if order_date is not None
                        else "発注日未設定のため新旧法の切替を確認してください。"
                    )
                ),
                citation_url="https://www.jftc.go.jp/partnership_package/toritekihou.html",
            )
        )

    # 建設業法の許可要件（高額・JV 時は要確認）
    if is_construction and (amount_jpy or 0) >= 150_000_000:
        laws.append(
            ApplicableLaw(
                law_code="construction_license_requirement",
                law_name="建設業許可（特定建設業）",
                applies=True,
                confidence=0.8,
                reason="請負代金が 1.5 億円以上のため、特定建設業許可の要否を確認してください。",
            )
        )

    return ApplicableLawResult(
        contract_id=contract_id,
        contract_type=ct,
        laws=laws,
    )


__all__ = ["ApplicableLaw", "ApplicableLawResult", "determine"]
