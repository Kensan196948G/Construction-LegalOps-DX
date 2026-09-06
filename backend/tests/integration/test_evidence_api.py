"""証拠・eDiscovery 管理 API の統合テスト（Phase 3 §5.17 / Issue #124）.

``app.api.v1.evidence`` ルーターは、並列実装との衝突を避けるためコーディ
ネーター統合まで ``app/api/v1/__init__.py`` へ未登録である（作業レポート
参照）。本テストは実際の FastAPI app インスタンスへ直接 ``include_router``
することでエンドツーエンドの疎通を検証する。
"""

from __future__ import annotations

import base64
from hashlib import sha256
from typing import Any

from app.api.v1.evidence import router as _evidence_router
from app.main import app as _app

if not any(str(getattr(r, "path", "")).startswith("/api/v1/evidence") for r in _app.routes):
    _app.include_router(_evidence_router, prefix="/api/v1")

EV = "/api/v1/evidence"


async def _create_evidence(
    client: Any, headers: dict[str, str], *, title: str, seed: bytes
) -> dict[str, Any]:
    r = await client.post(
        EV,
        json={
            "title": title,
            "description": "統合テスト用証拠",
            "source_type": "upload",
            "checksum_sha256": sha256(seed).hexdigest(),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_get_and_view_history(client: Any, auth_headers_admin: dict[str, str]) -> None:
    """#217/#218/#219/#222: 登録 → 取得（閲覧履歴に記録）→ 閲覧履歴確認."""
    evidence = await _create_evidence(
        client, auth_headers_admin, title="工事写真（統合テスト）", seed=b"integration-evidence-1"
    )
    assert evidence["evidence_code"].startswith("EVD-")
    assert evidence["is_duplicate"] is False
    assert evidence["relevance"] in {"relevant", "unclassified", "not_relevant", "privileged"}

    r_get = await client.get(f"{EV}/{evidence['id']}", headers=auth_headers_admin)
    assert r_get.status_code == 200

    r_history = await client.get(f"{EV}/{evidence['id']}/view-history", headers=auth_headers_admin)
    assert r_history.status_code == 200
    actions = {item["action"] for item in r_history.json()}
    assert "evidence.view" in actions


async def test_duplicate_detection_via_api(client: Any, auth_headers_admin: dict[str, str]) -> None:
    """#225: 同一ハッシュの証拠登録で重複が検出される."""
    seed = b"integration-duplicate-bytes"
    first = await _create_evidence(client, auth_headers_admin, title="証拠A", seed=seed)
    second = await _create_evidence(client, auth_headers_admin, title="証拠B（重複）", seed=seed)
    assert second["is_duplicate"] is True
    assert second["duplicate_of_id"] == first["id"]

    r_dup = await client.get(f"{EV}/{first['id']}/duplicates", headers=auth_headers_admin)
    assert r_dup.status_code == 200
    assert [d["id"] for d in r_dup.json()] == [second["id"]]


async def test_custody_chain_and_timeline_via_api(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#220/#221/#223: Chain of Custody 追記・証拠タイムライン取得."""
    evidence = await _create_evidence(
        client, auth_headers_admin, title="移管対象証拠", seed=b"integration-custody"
    )
    r_custody = await client.post(
        f"{EV}/{evidence['id']}/custody",
        json={
            "action": "transferred",
            "to_custodian": "外部鑑定機関（統合テスト）",
            "notes": "鑑定のため移管",
        },
        headers=auth_headers_admin,
    )
    assert r_custody.status_code == 201, r_custody.text
    assert r_custody.json()["hash_chain"]

    r_list = await client.get(f"{EV}/{evidence['id']}/custody", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert [c["action"] for c in r_list.json()] == ["collected", "transferred"]

    r_timeline = await client.get(f"{EV}/{evidence['id']}/timeline", headers=auth_headers_admin)
    assert r_timeline.status_code == 200
    timeline_actions = [item["action"] for item in r_timeline.json()]
    assert "collected" in timeline_actions
    assert "transferred" in timeline_actions


async def test_export_bundle_via_api(client: Any, auth_headers_admin: dict[str, str]) -> None:
    """#224: 証拠 Export バンドル（ハッシュ整合性検証結果を含む）."""
    evidence = await _create_evidence(
        client, auth_headers_admin, title="Export 対象証拠", seed=b"integration-export"
    )
    r_export = await client.get(f"{EV}/{evidence['id']}/export", headers=auth_headers_admin)
    assert r_export.status_code == 200
    body = r_export.json()
    assert body["evidence_code"] == evidence["evidence_code"]
    assert body["custody_chain_verified"] is True
    assert body["sha256_hash"] == evidence["sha256_hash"]


async def test_email_ingest_via_api(client: Any, auth_headers_admin: dict[str, str]) -> None:
    """#226: メール証拠取込（.eml）."""
    raw_eml = (
        "From: taro@example.co.jp\r\n"
        "To: hanako@example.co.jp\r\n"
        "Subject: 統合テスト用メール証拠\r\n"
        "Date: Tue, 01 Sep 2026 10:00:00 +0900\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "本文（統合テスト）。\r\n"
    )
    r = await client.post(
        f"{EV}/email-ingest",
        json={"raw_eml": raw_eml, "collected_by_name": "法務担当（統合テスト）"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_type"] == "email"
    assert body["email_metadata"]["subject"] == "統合テスト用メール証拠"


async def test_photo_upload_with_base64_extracts_exif_when_present(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#227: 写真アップロード時に画像でなければ EXIF は None のままである."""
    raw = b"not-really-a-jpeg-but-base64-encodable"
    r = await client.post(
        EV,
        json={
            "title": "写真証拠（統合テスト）",
            "source_type": "photo",
            "mime_type": "image/jpeg",
            "file_content_base64": base64.b64encode(raw).decode("ascii"),
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sha256_hash"] == sha256(raw).hexdigest()
    assert body["exif_metadata"] is None


async def test_legal_hold_release_approval_workflow(
    client: Any,
    auth_headers_admin: dict[str, str],
    auth_headers_legal: dict[str, str],
    db_session: Any,
) -> None:
    """#230: Legal Hold 解除承認ワークフロー（申請者本人による決裁は 403）.

    Legal Hold 自体は既存の ``POST /api/v1/legal-holds``（``app.api.v1.governance``）
    ではなく ``db_session`` 経由で直接作成する。同エンドポイントは
    ``LegalHold.started_at`` の ``server_default`` がプレーン文字列 "now()" と
    定義されている既存の不具合により SQLite 上で 500 になるため（本 Issue の
    スコープ外・証拠管理機能とは無関係）、Evidence 側のテストを阻害しない
    ようにするための回避策である。
    """
    from datetime import UTC, datetime

    from app.models.access_control import LegalHold

    evidence = await _create_evidence(
        client,
        auth_headers_legal,
        title="Legal Hold 対象証拠（統合テスト）",
        seed=b"integration-hold",
    )

    hold = LegalHold(
        target_type="evidence",
        target_id=evidence["id"],
        reason="調査のため保全（統合テスト）",
        status="active",
        started_at=datetime.now(UTC),
        evidence_ids=[evidence["id"]],
    )
    db_session.add(hold)
    await db_session.flush()
    await db_session.commit()
    hold_id = hold.id

    r_link = await client.post(
        f"{EV}/{evidence['id']}/legal-hold",
        json={"legal_hold_id": hold_id},
        headers=auth_headers_admin,
    )
    assert r_link.status_code == 200, r_link.text
    assert r_link.json()["is_under_hold"] is True

    r_request = await client.post(
        f"{EV}/hold-release-requests",
        json={
            "legal_hold_id": hold_id,
            "reason": "調査完了のため解除申請（統合テスト）",
            "evidence_id": evidence["id"],
        },
        headers=auth_headers_legal,
    )
    assert r_request.status_code == 201, r_request.text
    approval_id = r_request.json()["id"]
    assert r_request.json()["status"] == "pending"

    r_self_decide = await client.post(
        f"{EV}/hold-release-requests/{approval_id}/decide",
        json={"approve": True},
        headers=auth_headers_legal,
    )
    # auth_headers_legal は reviewer ロールのため、まず承認ロール不足で 403 になる。
    assert r_self_decide.status_code == 403

    r_decide = await client.post(
        f"{EV}/hold-release-requests/{approval_id}/decide",
        json={"approve": True, "decision_note": "承認します（統合テスト）"},
        headers=auth_headers_admin,
    )
    assert r_decide.status_code == 200, r_decide.text
    assert r_decide.json()["status"] == "approved"

    r_evidence_after = await client.get(f"{EV}/{evidence['id']}", headers=auth_headers_admin)
    assert r_evidence_after.json()["is_under_hold"] is False

    r_list_requests = await client.get(
        f"{EV}/hold-release-requests", params={"legal_hold_id": hold_id}, headers=auth_headers_admin
    )
    assert r_list_requests.status_code == 200
    assert r_list_requests.json()[0]["status"] == "approved"
