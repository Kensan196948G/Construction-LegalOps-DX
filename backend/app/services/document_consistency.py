"""契約パッケージ文書間の矛盾検出（評価: 優先度 高 #2）.

契約書・約款・特記仕様書・設計図書・見積書等を一つのパッケージとして
扱い、金額・工期・責任分担の矛盾を優先順位付きで検出する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class DocumentConsistencyFinding:
    code: str
    severity: str  # block | warn | info
    message: str
    docs: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentSnapshot:
    id: int | None
    doc_type: str
    title: str
    priority: int
    amount_jpy: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = None


_AMOUNT_RE = re.compile(r"([\d,]+(?:\.[\d]+)?)\s*(億|万)?\s*円")


def _parse_amounts(text: str) -> list[int]:
    values: list[int] = []
    if not text:
        return values
    for m in _AMOUNT_RE.finditer(text):
        try:
            num = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2) or ""
        mult = {"億": 100_000_000, "万": 10_000}.get(unit, 1)
        values.append(int(num * mult))
    return values


def check_consistency(documents: list[DocumentSnapshot]) -> list[DocumentConsistencyFinding]:
    """文書パッケージの矛盾を検出する。"""
    findings: list[DocumentConsistencyFinding] = []
    docs = sorted(documents, key=lambda d: (d.priority, d.id or 0))
    if not docs:
        return findings

    # 金額矛盾: 最上位文書の金額と他文書の明示金額を比較
    top = docs[0]
    if top.amount_jpy is not None:
        for other in docs[1:]:
            if other.amount_jpy is None:
                continue
            deviation = abs(other.amount_jpy - top.amount_jpy) / max(top.amount_jpy, 1)
            if deviation > 0.2:
                findings.append(
                    DocumentConsistencyFinding(
                        code="document_amount_mismatch",
                        severity="warn",
                        message=(
                            f"{other.title}（{other.doc_type}）の金額 "
                            f"{other.amount_jpy:,} 円が上位文書 {top.title} の "
                            f"{top.amount_jpy:,} 円と 20% 超乖離しています。"
                        ),
                        docs=[top.title, other.title],
                        detail={
                            "top_amount": top.amount_jpy,
                            "other_amount": other.amount_jpy,
                            "deviation": round(deviation, 4),
                        },
                    )
                )

    # 金額が未構造化（本文のみ）の場合の相互比較
    amounts: list[tuple[DocumentSnapshot, list[int]]] = [
        (d, _parse_amounts(d.content or "")) for d in docs if d.content
    ]
    for doc, values in amounts:
        if len(values) >= 2 and len(set(values)) > 1:
            findings.append(
                DocumentConsistencyFinding(
                    code="document_amount_text_conflict",
                    severity="info",
                    message=(
                        f"{doc.title} の本文中に異なる金額が複数記載されています: "
                        + ", ".join(f"{v:,} 円" for v in sorted(set(values), reverse=True))
                    ),
                    docs=[doc.title],
                    detail={"amounts": values},
                )
            )

    # 工期矛盾: end < start
    for doc in docs:
        if (
            doc.start_date is not None
            and doc.end_date is not None
            and doc.end_date < doc.start_date
        ):
            findings.append(
                DocumentConsistencyFinding(
                    code="document_schedule_reversed",
                    severity="block",
                    message=(
                        f"{doc.title} の工期が逆転しています"
                        f"（{doc.start_date.isoformat()} → {doc.end_date.isoformat()}）。"
                    ),
                    docs=[doc.title],
                )
            )

    # 責任分担: 約款と特記仕様書で「甲の負担」「乙の負担」が両方書かれている項目
    for keyword in ("損害", "保険", "瑕疵", "手続"):
        holders: dict[str, list[str]] = {}
        for doc in docs:
            content = doc.content or ""
            if re.search(r"甲の(負担|責め|責)", content) and keyword in content:
                holders.setdefault("甲:" + keyword, []).append(doc.title)
            if re.search(r"乙の(負担|責め|責)", content) and keyword in content:
                holders.setdefault("乙:" + keyword, []).append(doc.title)
        for key, titles in holders.items():
            if len(titles) >= 2:
                findings.append(
                    DocumentConsistencyFinding(
                        code="document_responsibility_conflict",
                        severity="warn",
                        message=(
                            f"「{key}」の責任帰属が複数文書に記載されています: "
                            + ", ".join(titles)
                        ),
                        docs=titles,
                    )
                )

    return findings


def to_dict(findings: list[DocumentConsistencyFinding]) -> list[dict[str, Any]]:
    return [
        {
            "code": f.code,
            "severity": f.severity,
            "message": f.message,
            "docs": f.docs,
            "detail": f.detail,
        }
        for f in findings
    ]


__all__ = ["DocumentConsistencyFinding", "DocumentSnapshot", "check_consistency", "to_dict"]
