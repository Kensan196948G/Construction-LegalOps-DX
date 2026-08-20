"""JPO 特許情報取得 API 連携（知財管理・競合ウォッチ・審査書類）の API 統合テスト.

デモモード（JPO_API_MODE=demo）前提で、外部 API を呼ばずに全エンドポイントを検証する。
"""

from __future__ import annotations

import uuid

_SUFFIX = uuid.uuid4().hex[:8]


async def test_ip_asset_lifecycle(client, auth_headers_admin):
    # 登録（JPO デモデータから初期情報取得）
    r = await client.post(
        "/api/v1/ip-assets",
        json={
            "application_number": "2026000001",
            "ip_type": "patent",
            "notes": f"統合テスト-{_SUFFIX}",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    asset_id = body["id"]
    assert body["application_number"] == "2026000001"
    assert body["invention_title"]
    assert body["status"] == "登録"  # デモの登録情報により登録ステータス
    assert body["registration_number"] == "7000001"
    assert body["jplatpat_url"]

    # 一覧
    r_list = await client.get("/api/v1/ip-assets", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    # 詳細
    r_get = await client.get(f"/api/v1/ip-assets/{asset_id}", headers=auth_headers_admin)
    assert r_get.status_code == 200
    assert r_get.json()["id"] == asset_id

    # 更新（メモ）
    r_patch = await client.patch(
        f"/api/v1/ip-assets/{asset_id}",
        json={"notes": f"更新メモ-{_SUFFIX}"},
        headers=auth_headers_admin,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["notes"] == f"更新メモ-{_SUFFIX}"

    # 同期
    r_sync = await client.post(
        f"/api/v1/ip-assets/{asset_id}/sync",
        headers=auth_headers_admin,
    )
    assert r_sync.status_code == 200, r_sync.text
    assert r_sync.json()["application_number"] == "2026000001"

    # 重複登録は 400
    r_dup = await client.post(
        "/api/v1/ip-assets",
        json={"application_number": "2026000001", "ip_type": "patent"},
        headers=auth_headers_admin,
    )
    assert r_dup.status_code == 400

    # 論理削除
    r_del = await client.delete(f"/api/v1/ip-assets/{asset_id}", headers=auth_headers_admin)
    assert r_del.status_code == 204


async def test_ip_watch_target_and_events(client, auth_headers_admin):
    # ウォッチ対象の登録
    r = await client.post(
        "/api/v1/ip-watch-targets",
        json={
            "name": f"デモ競合会社-{_SUFFIX}",
            "applicant_code": "000000002",
            "ip_types": ["patent"],
            "status": "active",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    target_id = r.json()["id"]

    # 対象に紐づく出願を登録（デモデータ 2026000003 = さくら土木の出願）
    r_asset = await client.post(
        "/api/v1/ip-assets",
        json={
            "application_number": "2026000003",
            "ip_type": "patent",
            "watch_target_id": target_id,
        },
        headers=auth_headers_admin,
    )
    assert r_asset.status_code == 201, r_asset.text

    # ウォッチ対象一覧（asset_count が入る）
    r_list = await client.get("/api/v1/ip-watch-targets", headers=auth_headers_admin)
    assert r_list.status_code == 200
    target_row = next(t for t in r_list.json()["items"] if t["id"] == target_id)
    assert target_row["asset_count"] >= 1

    # 同期 → 差分イベント生成（登録時から変化なしでもステータス遷移がある場合は生成される）
    r_sync = await client.post(
        f"/api/v1/ip-watch-targets/{target_id}/sync",
        headers=auth_headers_admin,
    )
    assert r_sync.status_code == 200, r_sync.text
    assert r_sync.json()["scanned_assets"] >= 1

    # イベント一覧
    r_events = await client.get(
        "/api/v1/ip-watch-events",
        params={"watch_target_id": target_id},
        headers=auth_headers_admin,
    )
    assert r_events.status_code == 200

    # 既読化
    if r_events.json()["total"] > 0:
        event_id = r_events.json()["items"][0]["id"]
        r_read = await client.patch(
            f"/api/v1/ip-watch-events/{event_id}/read",
            headers=auth_headers_admin,
        )
        assert r_read.status_code == 200
        assert r_read.json()["is_read"] is True

    # 更新
    r_patch = await client.patch(
        f"/api/v1/ip-watch-targets/{target_id}",
        json={"status": "paused"},
        headers=auth_headers_admin,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["status"] == "paused"

    # 論理削除（asset は残る）
    r_del = await client.delete(f"/api/v1/ip-watch-targets/{target_id}", headers=auth_headers_admin)
    assert r_del.status_code == 204


async def test_ip_documents_fetch_and_analyze(client, auth_headers_admin):
    # 出願を登録（デモデータ 2026000004 を使用。拒絶理由通知書はデモ ZI で固定生成される）
    r = await client.post(
        "/api/v1/ip-assets",
        json={
            "application_number": "2026000004",
            "ip_type": "patent",
            "notes": f"書類テスト-{_SUFFIX}",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    asset_id = r.json()["id"]

    # 書類収集（拒絶理由通知書 + 意見書 + 発送書類 + 引用文献）
    r_fetch = await client.post(
        f"/api/v1/ip-assets/{asset_id}/documents/fetch",
        json={"doc_types": ["refusal_reason", "opinion_amendment", "decision", "citation"]},
        headers=auth_headers_admin,
    )
    assert r_fetch.status_code == 200, r_fetch.text
    body = r_fetch.json()
    assert len(body["fetched"]) == 4
    assert body["errors"] == []

    # 書類一覧
    r_list = await client.get(f"/api/v1/ip-assets/{asset_id}/documents", headers=auth_headers_admin)
    assert r_list.status_code == 200
    docs = r_list.json()
    assert len(docs) == 4
    refusal = next(d for d in docs if d["doc_type"] == "refusal_reason")
    assert refusal["content_text"]
    doc_id = refusal["id"]

    # AI 解析（デモモードの決定論的解析）
    r_analyze = await client.post(
        f"/api/v1/ip-documents/{doc_id}/analyze",
        headers=auth_headers_admin,
    )
    assert r_analyze.status_code == 200, r_analyze.text
    analysis = r_analyze.json()
    assert analysis["doc_type"] == "refusal_reason"
    assert analysis["summary"]
    assert analysis["findings"]["issues"]
    assert analysis["findings"]["deadline"] is not None
    assert analysis["ai_model"] == "demo-local"

    # 書類詳細（解析結果込み）
    r_get = await client.get(f"/api/v1/ip-documents/{doc_id}", headers=auth_headers_admin)
    assert r_get.status_code == 200
    assert r_get.json()["ai_summary"]


async def test_ip_dashboard_and_status(client, auth_headers_admin):
    r_dash = await client.get("/api/v1/ip-dashboard", headers=auth_headers_admin)
    assert r_dash.status_code == 200
    body = r_dash.json()
    assert "total_assets" in body
    assert "by_type" in body
    assert "api_mode" in body
    assert body["api_mode"] == "demo"
    assert body["api_configured"] is False

    r_status = await client.get("/api/v1/ip/jpo-status", headers=auth_headers_admin)
    assert r_status.status_code == 200
    assert r_status.json()["mode"] == "demo"
    assert r_status.json()["configured"] is False


async def test_ip_assets_requires_auth(client):
    r = await client.get("/api/v1/ip-assets")
    assert r.status_code in (401, 403)
