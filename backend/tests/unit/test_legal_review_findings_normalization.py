"""``ReviewDetail.findings`` の後方互換正規化のテスト.

背景（2026-09-28 実測）: ``legal_reviews.result``（JSONB）に旧形式の issue
（``{"detail", "target", "summary", "severity"}``）が残っていると、
``ReviewIssue`` が必須とする ``clause_seq`` / ``risk_level`` / ``comment`` を
満たせず ResponseValidationError となり ``GET /reviews`` が 500 を返していた
（MVP / prod の 2026-08-01 投入行 15 件が該当）。

読み取り時に正規化して 500 を防ぐ。新形式データの意味は変えない。
"""

from __future__ import annotations

from typing import Any

from app.schemas.legal_review import ReviewDetail
from app.schemas.review import ReviewOut

_BASE: dict[str, Any] = {
    "id": 1,
    "contract_id": 1,
    "review_type": "ai",
    "status": "completed",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def _validate(findings: Any) -> ReviewDetail:
    return ReviewOut.model_validate({**_BASE, "findings": findings})


def test_legacy_finding_is_mapped_to_current_shape() -> None:
    """旧形式 issue が risk_level / comment / title / clause_seq に写像される."""
    detail = _validate(
        [
            {
                "detail": "支払期日が納品後60日を超えている。",
                "target": "第3条 契約金額",
                "summary": "支払条件が下請法に抵触する可能性",
                "severity": "high",
            }
        ]
    )

    finding = detail.findings[0]
    assert finding.risk_level.value == "high"
    assert finding.comment == "支払期日が納品後60日を超えている。"
    assert finding.title == "支払条件が下請法に抵触する可能性"
    assert finding.clause_seq == 3
    # 旧形式に無い任意項目は既定値のまま
    assert finding.suggestion is None
    assert finding.citations == []


def test_legacy_finding_without_parsable_target_uses_clause_seq_zero() -> None:
    """``target`` から条番号を抽出できない場合は 0（条項に紐付かない指摘）."""
    detail = _validate(
        [{"detail": "d", "target": "別紙仕様書", "summary": "s", "severity": "medium"}]
    )

    assert detail.findings[0].clause_seq == 0
    # title が入るので frontend は「第0条」を表示しない
    assert detail.findings[0].title == "s"


def test_legacy_finding_without_target_uses_clause_seq_zero() -> None:
    detail = _validate([{"detail": "d", "severity": "low"}])
    assert detail.findings[0].clause_seq == 0


def test_new_format_finding_is_unchanged() -> None:
    """新形式は意味が変わらない（退行防止）."""
    detail = _validate(
        [
            {
                "clause_seq": 7,
                "title": "t",
                "risk_level": "critical",
                "comment": "c",
                "suggestion": "s",
                "citations": ["建設業法第19条の3"],
                "verdict": "needs_human_review",
                "suggested_actions": [
                    {"action": "counter_proposal", "description": "修正案を提示"}
                ],
            }
        ]
    )

    finding = detail.findings[0]
    assert finding.clause_seq == 7
    assert finding.title == "t"
    assert finding.risk_level.value == "critical"
    assert finding.comment == "c"
    assert finding.suggestion == "s"
    assert finding.citations == ["建設業法第19条の3"]
    assert finding.verdict == "needs_human_review"
    assert finding.suggested_actions[0].action == "counter_proposal"


def test_new_format_keys_win_over_legacy_keys() -> None:
    """新旧キーが混在する場合は現行キーを優先する."""
    detail = _validate(
        [
            {
                "clause_seq": 2,
                "risk_level": "low",
                "comment": "現行",
                "severity": "critical",
                "detail": "旧",
            }
        ]
    )

    finding = detail.findings[0]
    assert finding.risk_level.value == "low"
    assert finding.comment == "現行"
    assert finding.clause_seq == 2


def test_broken_entries_are_skipped_without_error() -> None:
    """壊れた要素は 500 にせず読み飛ばし、正常な要素だけ残す."""
    detail = _validate(
        [
            "not-a-dict",
            None,
            123,
            {},  # risk_level / comment を補えない
            {"severity": "unknown-value", "detail": "d"},  # risk_level を補えない
            {"severity": "high", "target": "第1条"},  # comment を補えない
            # clause_seq が不正でも target からの再抽出（不能なら 0）で救うため
            # 読み飛ばさない
            {"clause_seq": -1, "risk_level": "high", "comment": "c", "target": "第4条"},
            {"clause_seq": 5, "risk_level": "high", "comment": "ok", "title": "keep"},
        ]
    )

    assert [f.comment for f in detail.findings] == ["c", "ok"]
    assert [f.clause_seq for f in detail.findings] == [4, 5]


def test_findings_missing_or_not_a_list_is_empty() -> None:
    assert _validate(None).findings == []
    assert _validate({"nope": 1}).findings == []
    assert _validate("broken").findings == []
    assert _validate([]).findings == []


def test_findings_accepts_review_issue_instances() -> None:
    """既に検証済みの ``ReviewIssue`` を渡しても落ちない（再検証経路）."""
    from app.schemas.legal_review import ReviewIssue

    original = ReviewIssue(clause_seq=1, risk_level="high", comment="c")
    detail = _validate([original])

    assert detail.findings[0].clause_seq == 1
    assert detail.findings[0].comment == "c"
