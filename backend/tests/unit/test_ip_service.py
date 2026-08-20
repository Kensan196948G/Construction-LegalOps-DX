"""知財サービス（台帳・ウォッチ・書類解析）のユニットテスト."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import ip_service
from app.services.ip_service import (
    _derive_status,
    _extract_deadline,
    _format_citations,
)


def test_derive_status_from_progress():
    progress = [
        {"progressCode": "110", "progressDate": "20260115"},
        {"progressCode": "210", "progressDate": "20260720"},
    ]
    assert _derive_status(progress) == "審査請求"


def test_derive_status_refusal():
    progress = [{"progressCode": "300", "progressDate": "20260901"}]
    assert _derive_status(progress) == "拒絶理由通知"


def test_derive_status_registration():
    progress = [{"progressCode": "400", "progressDate": "20260930"}]
    assert _derive_status(progress) == "登録"


def test_derive_status_empty():
    assert _derive_status([]) == "unknown"


def test_extract_deadline():
    text = (
        "【通知日】2026年9月1日"
        "\n【指定期間】この通知の発送の日から3月以内に"
        "意見書又は補正書を提出すること。"
    )
    d = _extract_deadline(text)
    assert d is not None
    assert d.year == 2026
    assert d.month == 12  # 9月 + 3ヶ月


def test_extract_deadline_missing():
    assert _extract_deadline("期限の記載なし") is None


def test_format_citations():
    data = {
        "patentDoc": {"documentNumber": "JP2020-123456A", "citationOrder": "1"},
        "nonPatentDoc": {"documentName": "建設工事の品質管理便覧"},
    }
    text = _format_citations(data)
    assert "JP2020-123456A" in text
    assert "建設工事の品質管理便覧" in text


# ---------------------------------------------------------------------------
# analyze_document（デモ解析）
# ---------------------------------------------------------------------------


def _doc(text: str, doc_type: str = "refusal_reason") -> MagicMock:
    d = MagicMock()
    d.id = 1
    d.ip_asset_id = 1
    d.doc_type = doc_type
    d.content_text = text
    d.ai_summary = None
    d.ai_findings = {}
    d.ai_model = None
    d.analyzed_at = None
    d.error = None
    return d


def test_analyze_document_demo_refusal():
    import asyncio

    session = AsyncMock()
    doc = _doc("【通知日】2026年9月1日\n拒絶理由通知書（デモ）\n特許法第29条第1項第3号\n3月以内")
    asyncio.run(ip_service.analyze_document(session, document=doc))
    assert doc.ai_summary
    assert doc.ai_findings["issues"]
    assert doc.analyzed_at is not None
    assert doc.ai_model == "demo-local"
    # 期限が検出されている
    assert doc.ai_findings["deadline"] is not None


def test_analyze_document_empty_text_raises():
    import asyncio

    session = AsyncMock()
    doc = _doc("   ")
    with pytest.raises(ip_service.IpServiceError):
        asyncio.run(ip_service.analyze_document(session, document=doc))


# ---------------------------------------------------------------------------
# register_asset / sync（デモクライアント + モックセッション）
# ---------------------------------------------------------------------------


class _FakeSession:
    """flush/refresh を実装した最小 AsyncMock セッション."""

    def __init__(self) -> None:
        self.add = MagicMock()
        self.flush = AsyncMock(return_value=None)
        self.refresh = AsyncMock(side_effect=lambda obj: obj)
        self.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None),
                scalars=MagicMock(return_value=[]),
                all=MagicMock(return_value=[]),
            )
        )
        self.get = AsyncMock(return_value=None)


def test_register_asset_demo():
    import asyncio

    from app.models.ip_asset import IpAsset

    session = _FakeSession()
    asset = asyncio.run(
        ip_service.register_asset(
            session,  # type: ignore[arg-type]
            application_number="2026000001",
            ip_type="patent",
            actor_id=1,
        )
    )
    assert isinstance(asset, IpAsset)
    assert asset.application_number == "2026000001"
    assert asset.invention_title == "建設現場の安全管理システム（デモ）"
    # デモの registration_info に登録番号 7000001 が含まれるため登録ステータスになる
    assert asset.status == "登録"
    assert asset.registration_number == "7000001"
    assert asset.last_synced_at is not None
    session.add.assert_called()


def test_register_asset_duplicate_raises():
    import asyncio

    existing = MagicMock()
    session = _FakeSession()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing),
            scalars=MagicMock(return_value=[]),
        )
    )
    with pytest.raises(ip_service.IpServiceError):
        asyncio.run(
            ip_service.register_asset(
                session,  # type: ignore[arg-type]
                application_number="2026000001",
            )
        )


def test_sync_asset_creates_watch_event_on_new_refusal():
    import asyncio

    from app.models.ip_asset import IpAsset

    asset = IpAsset(
        application_number="2026000003",
        ip_type="patent",
        watch_target_id=1,
        progress_data={
            "progress": [
                {"progressCode": "110", "progressDate": "20260305"},
                {"progressCode": "160", "progressDate": "20260801"},
            ]
        },
        status="公開",
    )
    session = _FakeSession()
    calls, events = asyncio.run(
        ip_service.sync_asset(
            session,  # type: ignore[arg-type]
            asset=asset,
            create_events=True,
        )
    )
    assert calls == 1
    assert events == 1
    # 拒絶理由通知（300）がデモデータに含まれるため status_change イベントが生成される
    assert asset.status == "拒絶理由通知"


def test_sync_watch_target_scans_all_assets():
    import asyncio

    from app.models.ip_asset import IpAsset
    from app.models.ip_watch import IpWatchTarget

    target = IpWatchTarget(id=1, name="さくら土木(株)")
    assets = [
        IpAsset(
            id=1,
            application_number="2026000003",
            ip_type="patent",
            watch_target_id=1,
            progress_data={"progress": [{"progressCode": "110", "progressDate": "20260305"}]},
            status="出願",
        ),
        IpAsset(
            id=2,
            application_number="2026000004",
            ip_type="patent",
            watch_target_id=1,
            progress_data={"progress": [{"progressCode": "110", "progressDate": "20260401"}]},
            status="出願",
        ),
    ]
    session = _FakeSession()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=assets))),
        )
    )
    calls, events, scanned = asyncio.run(
        ip_service.sync_watch_target(
            session,  # type: ignore[arg-type]
            target=target,
        )
    )
    assert scanned == 2
    assert calls == 2
    assert events == 1  # 2026000003 に拒絶理由通知が追加される


def test_jpo_status_shape():
    status = ip_service.jpo_status()
    assert set(status) == {
        "mode",
        "configured",
        "base_url",
        "max_calls_per_minute",
    }
    assert status["mode"] == "demo"
    assert status["configured"] is False
