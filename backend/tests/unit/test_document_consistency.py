"""契約文書パッケージの整合性チェック（金額・工期・責任分担）のユニットテスト."""

from __future__ import annotations

from datetime import date

from app.services.document_consistency import DocumentSnapshot, check_consistency


def _snap(**kwargs) -> DocumentSnapshot:
    return DocumentSnapshot(
        id=kwargs.get("id", 1),
        doc_type=kwargs.get("doc_type", "contract"),
        title=kwargs.get("title", "文書"),
        priority=kwargs.get("priority", 1),
        amount_jpy=kwargs.get("amount_jpy"),
        start_date=kwargs.get("start_date"),
        end_date=kwargs.get("end_date"),
        content=kwargs.get("content"),
    )


def test_amount_mismatch_detected():
    docs = [
        _snap(id=1, doc_type="contract", title="契約書", priority=1, amount_jpy=10000000),
        _snap(id=2, doc_type="quotation", title="見積書", priority=5, amount_jpy=13000000),
    ]
    findings = check_consistency(docs)
    assert any(f.code == "document_amount_mismatch" for f in findings)


def test_schedule_reversed_detected():
    docs = [
        _snap(
            id=1,
            doc_type="contract",
            title="契約書",
            priority=1,
            start_date=date(2026, 12, 31),
            end_date=date(2026, 8, 1),
        ),
    ]
    findings = check_consistency(docs)
    assert any(f.code == "document_schedule_reversed" for f in findings)
    assert findings[0].severity == "block"


def test_responsibility_conflict_detected():
    docs = [
        _snap(
            id=1,
            doc_type="contract",
            title="契約書",
            priority=1,
            content="瑕疵については甲の責めに帰する。",
        ),
        _snap(
            id=2,
            doc_type="special_specifications",
            title="特記仕様書",
            priority=3,
            content="瑕疵の補修費用は甲の責めに帰する。",
        ),
    ]
    findings = check_consistency(docs)
    assert any(f.code == "document_responsibility_conflict" for f in findings)


def test_amount_text_conflict_detected():
    docs = [
        _snap(
            id=1,
            doc_type="contract",
            title="契約書",
            priority=1,
            content="請負代金は 10,000,000 円。ただし特記による増額後は 12,000,000 円。",
        ),
    ]
    findings = check_consistency(docs)
    assert any(f.code == "document_amount_text_conflict" for f in findings)


def test_consistent_documents_no_findings():
    docs = [
        _snap(
            id=1,
            doc_type="contract",
            title="契約書",
            priority=1,
            amount_jpy=10000000,
        ),
        _snap(
            id=2,
            doc_type="special_specifications",
            title="特記仕様書",
            priority=3,
            amount_jpy=10000000,
        ),
    ]
    assert check_consistency(docs) == []
