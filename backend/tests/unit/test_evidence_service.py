"""証拠・eDiscovery 管理サービスの単体テスト（Phase 3 §5.17 / Issue #124）."""

from __future__ import annotations

import base64
import struct
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.access_control import LegalHold
from app.models.audit_log import AuditLog
from app.models.contract import Contract
from app.models.department import Department
from app.models.matter import LegalMatter
from app.models.user import User
from app.services import evidence_service


async def _seed_user(db_session, *, role: str = "reviewer") -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="証拠管理担当者",
        role=role,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return int(user.id)


async def _seed_contract(db_session, *, drafter_id: int) -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="工事部")
    db_session.add(dept)
    await db_session.flush()
    contract = Contract(
        contract_no=f"CTR-EVD-{uuid4().hex[:6]}",
        title="証拠テスト契約",
        counterparty="テスト（デモ）",
        contract_type="工事請負契約",
        amount=1_000_000,
        department_id=dept.id,
        drafter_id=drafter_id,
        status="approved",
    )
    db_session.add(contract)
    await db_session.flush()
    return int(contract.id)


async def _seed_matter(db_session) -> int:
    matter = LegalMatter(
        matter_no=f"MAT-EVD-{uuid4().hex[:6]}",
        title="証拠テスト案件",
        matter_type="dispute",
        opened_at=datetime.now(UTC),
    )
    db_session.add(matter)
    await db_session.flush()
    return int(matter.id)


def _build_minimal_jpeg_with_exif() -> bytes:
    """APP1/TIFF セグメントを含む最小の合成 JPEG バイト列を作る（Pillow 不使用テスト用）."""
    make = b"TestCam\x00"
    model = b"X100\x00"
    # IFD0: 2 entries (Make=0x010F, Model=0x0110), inline (<=4 bytes) ASCII
    # Make/Model はどちらも短いのでオフセット参照にして単純化する。
    tiff_header = b"II" + struct.pack("<HI", 42, 8)
    num_entries = 2
    ifd = struct.pack("<H", num_entries)
    entries_offset = 8 + 2 + num_entries * 12 + 4
    make_offset = entries_offset
    model_offset = make_offset + len(make)
    entry_make = struct.pack("<HHI", 0x010F, 2, len(make)) + struct.pack("<I", make_offset)
    entry_model = struct.pack("<HHI", 0x0110, 2, len(model)) + struct.pack("<I", model_offset)
    next_ifd = struct.pack("<I", 0)
    tiff = tiff_header + ifd + entry_make + entry_model + next_ifd + make + model

    exif_segment = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif_segment) + 2) + exif_segment
    return b"\xff\xd8" + app1 + b"\xff\xd9"


# ---------------------------------------------------------------------------
# ハッシュ・EXIF・関連性分類（純粋関数）
# ---------------------------------------------------------------------------


def test_compute_sha256_matches_hashlib() -> None:
    data = b"evidence-bytes"
    assert evidence_service.compute_sha256(data) == sha256(data).hexdigest()


def test_extract_exif_returns_none_for_non_jpeg() -> None:
    assert evidence_service.extract_exif(b"not-a-jpeg") is None


def test_extract_exif_parses_make_and_model() -> None:
    jpeg = _build_minimal_jpeg_with_exif()
    exif = evidence_service.extract_exif(jpeg)
    assert exif is not None
    assert exif.get("make") == "TestCam"
    assert exif.get("model") == "X100"


def test_classify_relevance_privileged_beats_relevant() -> None:
    relevance, score, note = evidence_service.classify_relevance(
        title="弁護士との契約変更協議メモ", description="支払・請求について相談"
    )
    assert relevance == "privileged"
    assert score >= 60
    assert "秘匿特権" in note


def test_classify_relevance_relevant_requires_two_keywords() -> None:
    relevance, _score, _note = evidence_service.classify_relevance(
        title="支払遅延に関するクレーム記録", description=None
    )
    assert relevance == "relevant"


def test_classify_relevance_not_relevant_when_no_keywords() -> None:
    relevance, score, _note = evidence_service.classify_relevance(
        title="社内懇親会のお知らせ", description="来週金曜開催"
    )
    assert relevance == "not_relevant"
    assert score == 10


# ---------------------------------------------------------------------------
# 証拠登録・重複検出・Chain of Custody・監査ログ
# ---------------------------------------------------------------------------


async def test_create_evidence_with_checksum_records_custody_and_audit(db_session) -> None:
    uid = await _seed_user(db_session)
    checksum = sha256(b"contract-photo-bytes").hexdigest()

    row = await evidence_service.create_evidence(
        db_session,
        actor_id=uid,
        title="工事写真（テスト）",
        description="支払遅延の証拠となる現場写真",
        source_type="photo",
        checksum_sha256=checksum,
        collected_by_name="現場監督（テスト）",
    )

    assert row.evidence_code.startswith(f"EVD-{datetime.now(UTC).year}-")
    assert row.sha256_hash == checksum
    assert row.is_duplicate is False
    assert row.relevance in {"relevant", "unclassified", "not_relevant", "privileged"}

    custody = await evidence_service.list_custody_events(db_session, evidence_id=row.id)
    assert len(custody) == 1
    assert custody[0].action == "collected"
    assert custody[0].previous_hash is None
    assert custody[0].hash_chain

    assert await evidence_service.verify_custody_chain(db_session, evidence_id=row.id) is True

    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "evidence",
                    AuditLog.target_id == row.id,
                )
            )
        )
        .scalars()
        .all()
    )
    actions = {r.action for r in audit_rows}
    assert "evidence.create" in actions
    assert "evidence.custody.collected" in actions
    for r in audit_rows:
        assert r.hash_chain  # SHA-256 ハッシュチェーンが記録されている


async def test_create_evidence_requires_content_or_checksum(db_session) -> None:
    uid = await _seed_user(db_session)
    with pytest.raises(ValidationError):
        await evidence_service.create_evidence(db_session, actor_id=uid, title="無効な証拠")


async def test_create_evidence_with_base64_content_computes_hash(db_session) -> None:
    uid = await _seed_user(db_session)
    raw = b"raw evidence file content"
    row = await evidence_service.create_evidence(
        db_session,
        actor_id=uid,
        title="アップロード証拠（テスト）",
        source_type="upload",
        file_content_base64=base64.b64encode(raw).decode("ascii"),
    )
    assert row.sha256_hash == sha256(raw).hexdigest()
    assert row.size_bytes == len(raw)


async def test_duplicate_detection_flags_second_evidence(db_session) -> None:
    uid = await _seed_user(db_session)
    checksum = sha256(b"duplicate-bytes").hexdigest()

    first = await evidence_service.create_evidence(
        db_session, actor_id=uid, title="証拠A（テスト）", checksum_sha256=checksum
    )
    second = await evidence_service.create_evidence(
        db_session, actor_id=uid, title="証拠B（テスト・同一ハッシュ）", checksum_sha256=checksum
    )

    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert second.duplicate_of_id == first.id

    dups = await evidence_service.list_duplicates(db_session, evidence_id=first.id)
    assert [d.id for d in dups] == [second.id]


async def test_matter_and_contract_linkage_and_not_found(db_session) -> None:
    uid = await _seed_user(db_session)
    contract_id = await _seed_contract(db_session, drafter_id=uid)
    matter_id = await _seed_matter(db_session)

    row = await evidence_service.create_evidence(
        db_session,
        actor_id=uid,
        title="契約関連証拠（テスト）",
        matter_id=matter_id,
        contract_id=contract_id,
        checksum_sha256=sha256(b"linked-evidence").hexdigest(),
    )
    assert row.matter_id == matter_id
    assert row.contract_id == contract_id

    with pytest.raises(NotFoundError):
        await evidence_service.create_evidence(
            db_session,
            actor_id=uid,
            title="存在しない案件への証拠",
            matter_id=999_999,
            checksum_sha256=sha256(b"missing-matter").hexdigest(),
        )


async def test_get_evidence_not_found(db_session) -> None:
    with pytest.raises(NotFoundError):
        await evidence_service.get_evidence(db_session, evidence_id=999_999)


# ---------------------------------------------------------------------------
# 証拠閲覧履歴・タイムライン・Export
# ---------------------------------------------------------------------------


async def test_view_history_and_timeline_and_export(db_session) -> None:
    uid = await _seed_user(db_session)
    row = await evidence_service.create_evidence(
        db_session,
        actor_id=uid,
        title="タイムライン確認用証拠（テスト）",
        checksum_sha256=sha256(b"timeline-evidence").hexdigest(),
    )

    await evidence_service.record_view(db_session, evidence_id=row.id, viewer_id=uid)
    await evidence_service.add_custody_event(
        db_session,
        evidence_id=row.id,
        actor_id=uid,
        action="transferred",
        to_custodian="外部鑑定機関（テスト）",
        notes="鑑定のため移管",
    )

    history, total = await evidence_service.get_view_history(db_session, evidence_id=row.id)
    assert total >= 1
    assert any(h.action == "evidence.view" for h in history)

    timeline = await evidence_service.get_timeline(db_session, evidence_id=row.id)
    occurred_ats = [item["occurred_at"] for item in timeline]
    assert occurred_ats == sorted(occurred_ats)
    assert any(item["action"] == "collected" for item in timeline)
    assert any(item["action"] == "transferred" for item in timeline)
    assert any(item["action"] == "evidence.view" for item in timeline)

    bundle = await evidence_service.export_evidence_bundle(
        db_session, evidence_id=row.id, actor_id=uid
    )
    assert bundle["evidence_code"] == row.evidence_code
    assert bundle["custody_chain_verified"] is True
    assert bundle["sha256_hash"] == row.sha256_hash
    # export バンドルは呼び出し時点のタイムラインを封入する（Export イベント
    # 自体の監査ログは Export 完了後に記録されるため、封入対象には含まれない）。
    assert len(bundle["timeline"]) == len(timeline)


async def test_add_custody_event_rejects_unknown_action(db_session) -> None:
    uid = await _seed_user(db_session)
    row = await evidence_service.create_evidence(
        db_session,
        actor_id=uid,
        title="不正アクションテスト用証拠",
        checksum_sha256=sha256(b"bad-action-evidence").hexdigest(),
    )
    with pytest.raises(ValidationError):
        await evidence_service.add_custody_event(
            db_session, evidence_id=row.id, actor_id=uid, action="bogus"
        )


# ---------------------------------------------------------------------------
# メール証拠取込
# ---------------------------------------------------------------------------


async def test_ingest_email_evidence_extracts_metadata(db_session) -> None:
    uid = await _seed_user(db_session)
    raw_eml = (
        "From: taro@example.co.jp\r\n"
        "To: hanako@example.co.jp\r\n"
        "Subject: 支払遅延に関するご相談（契約変更）\r\n"
        "Date: Mon, 01 Sep 2026 09:00:00 +0900\r\n"
        "Message-ID: <abc123@example.co.jp>\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "契約の支払条件についてご相談があります。\r\n"
    )
    row = await evidence_service.ingest_email_evidence(
        db_session, actor_id=uid, raw_eml=raw_eml, collected_by_name="法務担当（テスト）"
    )
    assert row.source_type == "email"
    assert row.email_metadata is not None
    assert row.email_metadata["subject"].startswith("支払遅延")
    assert row.sha256_hash == sha256(raw_eml.encode("utf-8")).hexdigest()

    with pytest.raises(ValidationError):
        await evidence_service.ingest_email_evidence(db_session, actor_id=uid, raw_eml="   ")


# ---------------------------------------------------------------------------
# Legal Hold 解除承認ワークフロー
# ---------------------------------------------------------------------------


async def _seed_active_hold(db_session, *, started_by: int) -> int:
    # NOTE: LegalHold.started_at の server_default はプレーン文字列 "now()" で
    # 定義されているため（app.models.access_control）、SQLite では INSERT
    # 時にリテラル文字列がそのまま返り値解釈されて失敗する。既存モデルの
    # 挙動には触れず、テスト側で明示的に値を渡して回避する。
    hold = LegalHold(
        target_type="evidence",
        target_id=1,
        reason="調査のため保全（テスト）",
        status="active",
        started_by=started_by,
        started_at=datetime.now(UTC),
    )
    db_session.add(hold)
    await db_session.flush()
    return int(hold.id)


async def test_hold_release_workflow_approve(db_session) -> None:
    requester = await _seed_user(db_session)
    approver = await _seed_user(db_session, role="approver")
    hold_id = await _seed_active_hold(db_session, started_by=requester)

    row = await evidence_service.create_evidence(
        db_session,
        actor_id=requester,
        title="Legal Hold 対象証拠（テスト）",
        checksum_sha256=sha256(b"hold-evidence").hexdigest(),
    )
    await evidence_service.link_legal_hold(
        db_session, evidence_id=row.id, legal_hold_id=hold_id, actor_id=requester
    )

    approval = await evidence_service.request_hold_release(
        db_session,
        legal_hold_id=hold_id,
        requested_by=requester,
        reason="調査完了のため解除申請（テスト）",
        evidence_id=row.id,
    )
    assert approval.status == "pending"

    with pytest.raises(ForbiddenError):
        await evidence_service.decide_hold_release(
            db_session, approval_id=approval.id, decided_by=requester, approve=True
        )

    with pytest.raises(ConflictError):
        await evidence_service.request_hold_release(
            db_session, legal_hold_id=hold_id, requested_by=requester, reason="二重申請（テスト）"
        )

    decided = await evidence_service.decide_hold_release(
        db_session,
        approval_id=approval.id,
        decided_by=approver,
        approve=True,
        decision_note="承認します（テスト）",
    )
    assert decided.status == "approved"

    released_hold = await db_session.get(LegalHold, hold_id)
    assert released_hold.status == "released"

    refreshed_evidence = await evidence_service.get_evidence(db_session, evidence_id=row.id)
    assert refreshed_evidence.is_under_hold is False

    with pytest.raises(ConflictError):
        await evidence_service.decide_hold_release(
            db_session, approval_id=approval.id, decided_by=approver, approve=True
        )


async def test_hold_release_reject(db_session) -> None:
    requester = await _seed_user(db_session)
    approver = await _seed_user(db_session, role="approver")
    hold_id = await _seed_active_hold(db_session, started_by=requester)

    approval = await evidence_service.request_hold_release(
        db_session, legal_hold_id=hold_id, requested_by=requester, reason="解除希望（テスト）"
    )
    decided = await evidence_service.decide_hold_release(
        db_session,
        approval_id=approval.id,
        decided_by=approver,
        approve=False,
        decision_note="保全継続が必要（テスト）",
    )
    assert decided.status == "rejected"
    hold = await db_session.get(LegalHold, hold_id)
    assert hold.status == "active"


async def test_request_hold_release_requires_active_hold(db_session) -> None:
    requester = await _seed_user(db_session)
    hold = LegalHold(
        target_type="evidence",
        target_id=2,
        reason="既に解除済み（テスト）",
        status="released",
        started_by=requester,
        started_at=datetime.now(UTC),
    )
    db_session.add(hold)
    await db_session.flush()

    with pytest.raises(ConflictError):
        await evidence_service.request_hold_release(
            db_session, legal_hold_id=hold.id, requested_by=requester, reason="再解除申請（テスト）"
        )
