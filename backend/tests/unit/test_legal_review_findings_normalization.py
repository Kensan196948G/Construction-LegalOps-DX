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


def _current_finding(**overrides: Any) -> dict[str, Any]:
    """現行形式の必須項目を満たす finding（任意項目だけを差し替えて使う）."""
    finding: dict[str, Any] = {"clause_seq": 1, "risk_level": "high", "comment": "c"}
    finding.update(overrides)
    return finding


def test_broken_optional_fields_are_dropped() -> None:
    """**任意項目**の型・値域違反も読み飛ばす（データ起因の 500 を防ぐ）.

    必須項目だけを見て採用すると、``citations: "不正な値"`` のような違反が
    素通りし、呼び出し元のレスポンス検証で 500 になる（CodeRabbit 指摘）。
    """
    detail = _validate(
        [
            _current_finding(citations="不正な値"),  # list[str] のはず
            _current_finding(citations=[1, 2]),  # 要素の型が違う
            _current_finding(ai_confidence="abc"),  # float 0..1 のはず
            _current_finding(ai_confidence=1.5),  # 値域外
            _current_finding(suggested_actions="x"),  # list[dict] のはず
            _current_finding(suggested_actions=[{"description": "d"}]),  # action 欠落
            _current_finding(verdict="bogus"),  # pattern 違反
            _current_finding(source_page="three"),  # int のはず
            # 正しい要素は残る
            _current_finding(
                clause_seq=9,
                citations=["建設業法第19条の3"],
                ai_confidence=0.8,
                verdict="needs_human_review",
                suggested_actions=[
                    {"action": "counter_proposal", "description": "修正案を提示"}
                ],
            ),
        ]
    )

    assert len(detail.findings) == 1
    kept = detail.findings[0]
    assert kept.clause_seq == 9
    assert kept.citations == ["建設業法第19条の3"]
    assert kept.ai_confidence == 0.8
    assert kept.verdict == "needs_human_review"
    assert kept.suggested_actions[0].action == "counter_proposal"


def test_legacy_finding_with_broken_optional_field_is_dropped() -> None:
    """旧形式でも任意項目が壊れていれば読み飛ばす（救済は必須項目が健全な場合のみ）."""
    detail = _validate(
        [
            {
                "detail": "d",
                "target": "第3条 x",
                "summary": "s",
                "severity": "high",
                "citations": "不正な値",
            },
            {"detail": "d2", "target": "第4条 y", "summary": "s2", "severity": "medium"},
        ]
    )

    assert [f.comment for f in detail.findings] == ["d2"]
    assert detail.findings[0].clause_seq == 4


def test_optional_field_type_violation_would_500_without_validation() -> None:
    """回帰の核: 候補を ``ReviewIssue`` で検証しないと 500 になることの証明.

    正規化（旧形式→現行形式の写像）だけでは型違反を検出できないため、
    ``_coerce_findings`` が最終検証している。ここでは「検証を挟まなければ
    落ちる」ことを直接示して、テストが有意義であることを固定する。
    """
    import pytest
    from pydantic import ValidationError

    from app.schemas.legal_review import ReviewIssue, _normalize_finding

    candidate = _normalize_finding(_current_finding(citations="不正な値"))
    assert candidate is not None  # 正規化は通過してしまう
    with pytest.raises(ValidationError):
        ReviewIssue.model_validate(candidate)

    # 正規化 + 検証を通す `_validate` 経由では落ちず、要素だけが読み飛ばされる
    assert _validate([_current_finding(citations="不正な値")]).findings == []
