"""価格転嫁・スライド条項シミュレータの計算サービス（ロードマップ #25/#26）.

- #26 価格転嫁シミュレータ: 労務費・材料費の変動率と転嫁率から、請負金額への
  影響額と調整後金額を決定論的に算出する（AI 不使用・DB 不要の純計算）。
- #25 スライド条項管理: 資材・労務費変動による契約金額のスライド調整は、
  本シミュレータの計算（構成比 × 変動率 × 転嫁率）と同一式で試算する。
  条項自体の有無・文言は契約条項（clauses）側で管理する。
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationError


def simulate_price_pass_through(
    *,
    contract_amount_jpy: int,
    labor_cost_jpy: int,
    material_cost_jpy: int,
    labor_change_rate: float,
    material_change_rate: float,
    pass_through_rate: float,
) -> dict[str, Any]:
    """価格転嫁シミュレーション（#26）.

    - labor/material_cost_jpy: 対象工事の労務費・材料費（円）
    - *_change_rate: 変動率（0.08 = 8% 上昇。下落は負値）
    - pass_through_rate: 転嫁率（0〜1・1 = 全額転嫁）

    返却: 各増減額・合計増減額・転嫁額・調整後請負金額（円未満切り捨て）。
    """
    if contract_amount_jpy < 0:
        raise ValidationError("請負金額は 0 以上です。")
    if labor_cost_jpy < 0 or material_cost_jpy < 0:
        raise ValidationError("労務費・材料費は 0 以上です。")
    if labor_change_rate < -1.0 or material_change_rate < -1.0:
        raise ValidationError("変動率は -100% 以上で指定してください。")
    if not 0.0 <= pass_through_rate <= 1.0:
        raise ValidationError("転嫁率は 0〜1（0〜100%）で指定してください。")

    labor_delta = labor_cost_jpy * labor_change_rate
    material_delta = material_cost_jpy * material_change_rate
    total_delta = labor_delta + material_delta
    pass_through_amount = int(total_delta * pass_through_rate)  # 円未満切り捨て
    adjusted_amount = contract_amount_jpy + pass_through_amount

    return {
        "contract_amount_jpy": contract_amount_jpy,
        "labor_cost_jpy": labor_cost_jpy,
        "material_cost_jpy": material_cost_jpy,
        "labor_change_rate": round(labor_change_rate, 4),
        "material_change_rate": round(material_change_rate, 4),
        "pass_through_rate": round(pass_through_rate, 4),
        "labor_delta_jpy": int(labor_delta),
        "material_delta_jpy": int(material_delta),
        "total_delta_jpy": int(total_delta),
        "pass_through_amount_jpy": pass_through_amount,
        "adjusted_amount_jpy": adjusted_amount,
        "direction": (
            "up" if pass_through_amount > 0 else ("down" if pass_through_amount < 0 else "flat")
        ),
    }


__all__ = ["simulate_price_pass_through"]
