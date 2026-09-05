"""見積書様式生成サービス（ロードマップ #27）.

国交省の標準請負契約約款・見積書様式（総括表・明細表）に沿った構造を、
入力された工種明細から**決定論的に**生成する（AI 不使用・純テンプレート処理）。

2025-12 改正対応: 明細に 労務費 / 材料費 / 安全衛生経費 / 法定福利費 の内訳を
含め、合計・消費税・総額を整合計算する。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.exceptions import ValidationError


def generate_estimate_form(
    *,
    title: str,
    contractor_name: str,
    items: list[dict[str, Any]],
    tax_rate: float = 0.10,
    generated_on: date | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """#27 見積書（総括表＋明細表）を生成する.

    items の各要素: {work_type, spec, quantity, unit, unit_price_jpy,
    labor_cost_jpy, material_cost_jpy, safety_cost_jpy, welfare_cost_jpy}
    （labor + material + safety + welfare = amount_jpy の整合を検証）。
    """
    if not title.strip():
        raise ValidationError("件名は必須です。")
    if not contractor_name.strip():
        raise ValidationError("請負者名は必須です。")
    if not 0 <= tax_rate <= 1:
        raise ValidationError("消費税率は 0〜1 で指定してください。")
    if not items:
        raise ValidationError("明細が 1 件以上必要です。")

    detail_rows: list[dict[str, Any]] = []
    total_labor = 0
    total_material = 0
    total_safety = 0
    total_welfare = 0
    subtotal = 0

    for idx, item in enumerate(items, start=1):
        work_type = str(item.get("work_type") or "").strip()
        if not work_type:
            raise ValidationError(f"明細 {idx}: 工種は必須です。")
        quantity = item.get("quantity")
        unit_price = item.get("unit_price_jpy")
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            raise ValidationError(f"明細 {idx}: 数量は正の数値です。")
        if not isinstance(unit_price, (int, float)) or unit_price < 0:
            raise ValidationError(f"明細 {idx}: 単価は 0 以上です。")
        amount = int(quantity * unit_price)

        labor = int(item.get("labor_cost_jpy") or 0)
        material = int(item.get("material_cost_jpy") or 0)
        safety = int(item.get("safety_cost_jpy") or 0)
        welfare = int(item.get("welfare_cost_jpy") or 0)
        breakdown = labor + material + safety + welfare
        if breakdown != amount:
            raise ValidationError(
                f"明細 {idx}（{work_type}）: 内訳合計 {breakdown:,} 円が"
                f"金額 {amount:,} 円と一致しません（労務費・材料費・安全衛生経費・"
                "法定福利費の合計を金額に合わせてください）。"
            )

        total_labor += labor
        total_material += material
        total_safety += safety
        total_welfare += welfare
        subtotal += amount
        detail_rows.append(
            {
                "seq": idx,
                "work_type": work_type,
                "spec": str(item.get("spec") or ""),
                "quantity": quantity,
                "unit": str(item.get("unit") or ""),
                "unit_price_jpy": int(unit_price),
                "amount_jpy": amount,
                "labor_cost_jpy": labor,
                "material_cost_jpy": material,
                "safety_cost_jpy": safety,
                "welfare_cost_jpy": welfare,
            }
        )

    tax = int(subtotal * tax_rate)
    grand_total = subtotal + tax
    labor_ratio = round(total_labor / subtotal, 4) if subtotal else 0.0

    # 様式テキスト（総括表→明細表の順・決定論的なフォーマット）
    lines: list[str] = [
        "【見積書（総括表）】",
        f"件名: {title.strip()}",
        f"請負者: {contractor_name.strip()}",
        f"作成日: {(generated_on or date.today()).isoformat()}",
        "",
        f"正味価額（小計）: {subtotal:,} 円",
        f"消費税等（{tax_rate * 100:.0f}%）: {tax:,} 円",
        f"総額（税込）: {grand_total:,} 円",
        "",
        "内訳（2025-12 改正様式・労務費/材料費/安全衛生経費/法定福利費）:",
        f"  労務費: {total_labor:,} 円（構成比 {labor_ratio * 100:.1f}%）",
        f"  材料費: {total_material:,} 円",
        f"  安全衛生経費: {total_safety:,} 円",
        f"  法定福利費: {total_welfare:,} 円",
        "",
        "【明細表】",
    ]
    for row in detail_rows:
        lines.append(
            f"  {row['seq']}. {row['work_type']} {row['spec']} — "
            f"{row['quantity']}{row['unit']} × {row['unit_price_jpy']:,} 円 = "
            f"{row['amount_jpy']:,} 円"
        )
    if notes:
        lines.append("")
        lines.append(f"備考: {notes.strip()}")

    return {
        "title": title.strip(),
        "contractor_name": contractor_name.strip(),
        "generated_on": (generated_on or date.today()).isoformat(),
        "subtotal_jpy": subtotal,
        "tax_rate": tax_rate,
        "tax_jpy": tax,
        "grand_total_jpy": grand_total,
        "labor_cost_jpy": total_labor,
        "material_cost_jpy": total_material,
        "safety_cost_jpy": total_safety,
        "welfare_cost_jpy": total_welfare,
        "labor_ratio": labor_ratio,
        "items": detail_rows,
        "formatted_text": "\n".join(lines),
    }


__all__ = ["generate_estimate_form"]
