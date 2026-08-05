"""法令改正影響分析（評価 AI 機能 #2）.

発注日（契約締結日）を軸に、取適法施行（2026-01-01）を跨ぐ契約が
新しいルールでどのコンプライアンス判定に影響を受けるかを列挙する。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract


async def analyze(
    session: AsyncSession,
    *,
    effective_date: date | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """effective_date 施行の法令で影響を受ける契約を抽出する。"""
    from app.services.compliance_checker import TORITEKI_EFFECTIVE_DATE

    effective_date = effective_date or TORITEKI_EFFECTIVE_DATE
    rows = (
        await session.execute(
            select(Contract)
            .where(Contract.deleted_at.is_(None))
            .order_by(Contract.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    impacted: list[dict[str, Any]] = []
    checked = 0
    for contract in rows:
        order_date = contract.order_date
        if order_date is None:
            continue
        checked += 1
        is_after = order_date >= effective_date
        reasons: list[str] = []

        # 旧下請法→取適法: 従業員数基準追加
        if not is_after and (contract.our_employees or 0) > 100:
            reasons.append(
                "従業員数基準（取適法）で委託事業者に該当する可能性があり、"
                "施行後に締結する同種契約では新ルールを適用してください。"
            )

        # 手形払い禁止（2026 年以降）
        meta = contract.extra_metadata or {}
        body = str(meta.get("body") or meta.get("text") or "")
        if not is_after and "手形" in body:
            reasons.append("手形払いの記載がある契約は、施行後の取引では禁止対象です。")

        # 支払期日 60 日超
        if (
            not is_after
            and contract.receipt_date is not None
            and contract.payment_date is not None
            and (contract.payment_date - contract.receipt_date).days > 60
        ):
            reasons.append("受領日から支払日まで 60 日超の契約は、新ルールで支払遅延に該当します。")

        # 労務費等内訳（改正建設業法 2025-12）
        if contract.contract_type in ("請負", "JV") and not any(
            k in body for k in ("労務費", "材料費", "安全衛生経費", "法定福利費")
        ):
            reasons.append("労務費等の内訳記載がない請負契約（改正建設業法 19 条対象）。")

        if reasons:
            impacted.append(
                {
                    "contract_id": contract.id,
                    "contract_no": contract.contract_no,
                    "title": contract.title,
                    "order_date": order_date.isoformat(),
                    "effective_date": effective_date.isoformat(),
                    "is_after_effective_date": is_after,
                    "impact_reasons": reasons,
                    "status": contract.status,
                }
            )

    return {
        "effective_date": effective_date.isoformat(),
        "law_changes": [
            "中小受託取引適正化法（取適法）施行 2026-01-01",
            "改正建設業法全面施行 2025-12-01",
        ],
        "contracts_checked": checked,
        "impacted_contracts": impacted,
        "impacted_count": len(impacted),
    }


__all__ = ["analyze"]
