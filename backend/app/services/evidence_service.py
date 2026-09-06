"""証拠・eDiscovery 管理の業務サービス（Phase 3 §5.17 / Issue #124・#217-230）.

Evidence Repository（証拠保管庫）・SHA-256 ハッシュ・Chain of Custody・
証拠閲覧履歴・重複ファイル検出・メール証拠取込・写真 EXIF 保持・
証拠タイムライン・証拠関連性のルールベース分類・Legal Hold 解除承認
ワークフローを扱う。

設計方針:

* SHA-256 ハッシュ計算は ``app.services.audit_anchor`` と同じ発想
  （改ざん検知の起点をハッシュに置く）を証拠ファイル本体に適用する。
* Chain of Custody は ``app.models.audit_log.AuditLog`` と同じ
  ハッシュチェーン方式（前レコードのハッシュ + 正規化ペイロード）を
  証拠単位で保持する追記専用ログとして実装する。
* 監査ログ（``audit_service.log``）への記録は、API 層からの二重呼び出しに
  依存せずサービス層で完結させる。証拠の完全性証跡は呼び出し経路
  （API・バッチ取込・将来のメール自動取込等）に関わらず保証する必要が
  あるためである（Issue #124 の受入れ条件）。
* AI 分類基盤が存在しないため、証拠関連性分類は決定論的なルールベース
  （キーワードスコアリング）で実装する。将来 AI 分類器に置き換える場合も
  本関数のシグネチャ（戻り値: 分類・スコア・根拠）は維持する。
* 写真 EXIF 保持は Pillow 等の画像ライブラリに依存せず、JPEG の
  APP1/TIFF セグメントを直接パースする軽量実装とする。
"""

from __future__ import annotations

import base64
import binascii
import struct
from datetime import UTC, datetime
from email import message_from_string
from email.message import Message
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.access_control import LegalHold
from app.models.audit_log import AuditLog
from app.models.contract import Contract
from app.models.enums import (
    EvidenceCustodyAction,
    EvidenceHoldApprovalStatus,
    EvidenceRelevance,
    EvidenceSourceType,
)
from app.models.evidence import Evidence, EvidenceCustodyEvent, EvidenceHoldReleaseApproval
from app.models.matter import LegalMatter
from app.services import access_control, audit_service

_ZERO_HASH = "0" * 64
_TARGET_TYPE = "evidence"

_ALLOWED_SOURCE = {s.value for s in EvidenceSourceType}
_ALLOWED_RELEVANCE = {r.value for r in EvidenceRelevance}

# M10 CodeRabbit 指摘対応: PostgreSQL RLS（migration 025）を補助するアプリ層の
# 認可判定で使う特権ロール（RLS 側の legalops_actor_role() IN ('admin',
# 'auditor') と揃える）。
_PRIVILEGED_ROLES = frozenset({"admin", "auditor"})
_ALLOWED_CUSTODY_ACTION = {a.value for a in EvidenceCustodyAction}

# ルールベース関連性分類（#228）のキーワード辞書。AI 不使用・決定論的。
_PRIVILEGED_KEYWORDS: tuple[str, ...] = (
    "弁護士",
    "顧問",
    "法律相談",
    "privileged",
    "attorney",
    "internal legal advice",
)
_RELEVANT_KEYWORDS: tuple[str, ...] = (
    "契約",
    "支払",
    "指示",
    "事故",
    "遅延",
    "クレーム",
    "変更",
    "検収",
    "請求",
    "違反",
)

_VIEW_ACTIONS: tuple[str, ...] = ("evidence.view", "evidence.export")


# ---------------------------------------------------------------------------
# ハッシュ・EXIF ユーティリティ
# ---------------------------------------------------------------------------


def compute_sha256(data: bytes) -> str:
    """証拠ファイル本体の SHA-256 ハッシュを計算する（#219）."""
    return sha256(data).hexdigest()


_EXIF_TAGS: dict[int, str] = {
    0x010F: "make",
    0x0110: "model",
    0x0112: "orientation",
    0x0132: "datetime",
    0x9003: "datetime_original",
}


def _parse_tiff(buf: bytes) -> dict[str, Any] | None:
    """TIFF ヘッダ（EXIF IFD0）から代表的なタグのみを抽出する."""
    if len(buf) < 8:
        return None
    endian = buf[0:2]
    if endian == b"II":
        fmt = "<"
    elif endian == b"MM":
        fmt = ">"
    else:
        return None
    try:
        (ifd_offset,) = struct.unpack(fmt + "I", buf[4:8])
        (count,) = struct.unpack(fmt + "H", buf[ifd_offset : ifd_offset + 2])
    except struct.error:
        return None

    result: dict[str, Any] = {}
    entry_base = ifd_offset + 2
    for i in range(count):
        entry = buf[entry_base + i * 12 : entry_base + (i + 1) * 12]
        if len(entry) < 12:
            break
        try:
            tag, typ, cnt = struct.unpack(fmt + "HHI", entry[0:8])
        except struct.error:
            continue
        name = _EXIF_TAGS.get(tag)
        if name is None:
            continue
        value_raw = entry[8:12]
        try:
            if typ == 2:  # ASCII
                if cnt <= 4:
                    text = value_raw[: max(cnt - 1, 0)].decode("ascii", errors="ignore")
                else:
                    (offset,) = struct.unpack(fmt + "I", value_raw)
                    text = buf[offset : offset + cnt - 1].decode("ascii", errors="ignore")
                cleaned = text.strip("\x00").strip()
                if cleaned:
                    result[name] = cleaned
            elif typ == 3:  # SHORT
                (val,) = struct.unpack(fmt + "H", value_raw[:2])
                result[name] = val
        except (struct.error, UnicodeDecodeError):  # pragma: no cover - defensive
            continue
    return result or None


def extract_exif(data: bytes) -> dict[str, Any] | None:
    """JPEG の APP1/EXIF セグメントから代表的なタグを軽量抽出する（#227）.

    Pillow 等の画像ライブラリに依存しない最小実装。JPEG 以外・EXIF 非搭載・
    パース不能な場合は ``None`` を返す（失敗を隠さず、単に「保持できる情報
    がない」ことを表す）。
    """
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if pos + 4 > len(data):
            break
        seg_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if marker == 0xDA:  # Start Of Scan — ヘッダ部終了
            break
        if marker == 0xE1 and data[pos + 4 : pos + 10] == b"Exif\x00\x00":
            exif_segment = data[pos + 10 : pos + 2 + seg_len]
            return _parse_tiff(exif_segment)
        pos += 2 + seg_len
    return None


# ---------------------------------------------------------------------------
# 採番・重複検出・関連性分類
# ---------------------------------------------------------------------------


async def _generate_evidence_code(session: AsyncSession) -> str:
    """``EVD-YYYY-NNNNNN`` 形式の Evidence ID を採番する（#218）."""
    year = datetime.now(UTC).year
    prefix = f"EVD-{year}-"
    count_stmt = (
        select(func.count()).select_from(Evidence).where(Evidence.evidence_code.like(f"{prefix}%"))
    )
    seq = int((await session.execute(count_stmt)).scalar_one()) + 1
    for _ in range(10):
        candidate = f"{prefix}{seq:06d}"
        exists = (
            await session.execute(select(Evidence.id).where(Evidence.evidence_code == candidate))
        ).scalar_one_or_none()
        if exists is None:
            return candidate
        seq += 1
    raise ConflictError("証拠 ID の採番に失敗しました（重複が解消できません）。")


async def _find_duplicate(
    session: AsyncSession, *, sha256_hash: str, exclude_id: int | None = None
) -> Evidence | None:
    """同一 SHA-256 ハッシュを持つ既存証拠を検索する（#225）."""
    stmt = select(Evidence).where(
        Evidence.sha256_hash == sha256_hash, Evidence.deleted_at.is_(None)
    )
    if exclude_id is not None:
        stmt = stmt.where(Evidence.id != exclude_id)
    stmt = stmt.order_by(Evidence.id.asc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


def classify_relevance(*, title: str, description: str | None) -> tuple[str, int, str]:
    """証拠関連性のルールベース分類（#228・AI 不使用の決定論的スコアリング）."""
    text = f"{title} {description or ''}"
    privileged_hits = sum(1 for kw in _PRIVILEGED_KEYWORDS if kw in text)
    if privileged_hits > 0:
        score = min(100, 60 + privileged_hits * 10)
        return (
            EvidenceRelevance.PRIVILEGED.value,
            score,
            f"秘匿特権キーワードを {privileged_hits} 件検出（ルールベース・要法務確認）。",
        )
    relevant_hits = sum(1 for kw in _RELEVANT_KEYWORDS if kw in text)
    if relevant_hits >= 2:
        score = min(100, 50 + relevant_hits * 10)
        return (
            EvidenceRelevance.RELEVANT.value,
            score,
            f"関連キーワードを {relevant_hits} 件検出（ルールベース）。",
        )
    if relevant_hits == 1:
        return (
            EvidenceRelevance.UNCLASSIFIED.value,
            40,
            "関連キーワードを 1 件のみ検出（要人手確認）。",
        )
    return (
        EvidenceRelevance.NOT_RELEVANT.value,
        10,
        "関連キーワード検出なし（ルールベース）。",
    )


# ---------------------------------------------------------------------------
# Chain of Custody
# ---------------------------------------------------------------------------


def _canonical_datetime(dt: datetime) -> str:
    """SQLite の DateTime ラウンドトリップで tzinfo が失われても再現できる
    正規化済み ISO 文字列を返す（tzinfo 無しは UTC とみなす）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _custody_canonical_payload(
    *,
    evidence_id: int,
    action: str,
    actor_id: int | None,
    actor_name: str | None,
    from_custodian: str | None,
    to_custodian: str | None,
    occurred_at: datetime,
    notes: str | None,
) -> str:
    return (
        f"{evidence_id}|{action}|{actor_id}|{actor_name or ''}|"
        f"{from_custodian or ''}|{to_custodian or ''}|"
        f"{_canonical_datetime(occurred_at)}|{notes or ''}"
    )


async def _append_custody_event(
    session: AsyncSession,
    *,
    evidence_id: int,
    action: str,
    actor_id: int | None,
    actor_name: str | None = None,
    from_custodian: str | None = None,
    to_custodian: str | None = None,
    notes: str | None = None,
    occurred_at: datetime | None = None,
) -> EvidenceCustodyEvent:
    if action not in _ALLOWED_CUSTODY_ACTION:
        raise ValidationError(f"不正な Chain of Custody アクションです: {action!r}")

    last_hash = (
        await session.execute(
            select(EvidenceCustodyEvent.hash_chain)
            .where(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(EvidenceCustodyEvent.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    previous_hash = last_hash or _ZERO_HASH
    occurred = occurred_at or datetime.now(UTC)
    canonical = _custody_canonical_payload(
        evidence_id=evidence_id,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        from_custodian=from_custodian,
        to_custodian=to_custodian,
        occurred_at=occurred,
        notes=notes,
    )
    hash_chain = sha256((previous_hash + canonical).encode("utf-8")).hexdigest()

    event = EvidenceCustodyEvent(
        evidence_id=evidence_id,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        from_custodian=from_custodian,
        to_custodian=to_custodian,
        occurred_at=occurred,
        notes=notes,
        previous_hash=None if previous_hash == _ZERO_HASH else previous_hash,
        hash_chain=hash_chain,
    )
    session.add(event)
    await session.flush()
    await audit_service.log(
        session,
        actor_id=actor_id,
        action=f"evidence.custody.{action}",
        target_type=_TARGET_TYPE,
        target_id=evidence_id,
        payload={"hash_chain": hash_chain, "to_custodian": to_custodian},
    )
    return event


async def add_custody_event(
    session: AsyncSession,
    *,
    evidence_id: int,
    actor_id: int | None,
    action: str,
    actor_name: str | None = None,
    from_custodian: str | None = None,
    to_custodian: str | None = None,
    notes: str | None = None,
) -> EvidenceCustodyEvent:
    """証拠の受け渡しイベントを追記する（API 向け公開関数）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    return await _append_custody_event(
        session,
        evidence_id=evidence.id,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        from_custodian=from_custodian,
        to_custodian=to_custodian,
        notes=notes,
    )


async def list_custody_events(
    session: AsyncSession, *, evidence_id: int
) -> list[EvidenceCustodyEvent]:
    evidence = await get_evidence(session, evidence_id=evidence_id)
    stmt = (
        select(EvidenceCustodyEvent)
        .where(EvidenceCustodyEvent.evidence_id == evidence.id)
        .order_by(EvidenceCustodyEvent.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def verify_custody_chain(session: AsyncSession, *, evidence_id: int) -> bool:
    """証拠のハッシュチェーンを先頭から再計算し、改ざんの有無を検証する."""
    rows = await list_custody_events(session, evidence_id=evidence_id)
    previous = _ZERO_HASH
    for row in rows:
        expected_prev = row.previous_hash or _ZERO_HASH
        if expected_prev != previous:
            return False
        canonical = _custody_canonical_payload(
            evidence_id=row.evidence_id,
            action=row.action,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            from_custodian=row.from_custodian,
            to_custodian=row.to_custodian,
            occurred_at=row.occurred_at,
            notes=row.notes,
        )
        recomputed = sha256((previous + canonical).encode("utf-8")).hexdigest()
        if recomputed != row.hash_chain:
            return False
        previous = row.hash_chain
    return True


# ---------------------------------------------------------------------------
# Evidence CRUD / 検索
# ---------------------------------------------------------------------------


async def get_evidence(session: AsyncSession, *, evidence_id: int) -> Evidence:
    row = await session.get(Evidence, evidence_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(f"証拠が見つかりません（id={evidence_id}）")
    return row


async def ensure_evidence_visible(
    session: AsyncSession, *, evidence: Evidence, viewer: Any
) -> None:
    """案件 ACL・Legal Hold 倫理壁に基づくアプリ層の認可チェック（M10）.

    PostgreSQL RLS（migration 025 の ``legalops_evidence_row_visible``）と同じ
    優先順位で判定する多層防御。RLS が効かない環境（SQLite・テスト）でも
    ``viewer`` ロールが未実装の案件 ACL・倫理壁を経ずに証拠へアクセスするのを
    防ぐ。閲覧不可の場合は ``ForbiddenError`` を送出する。
    """
    role = getattr(viewer, "role", "guest")
    actor_id = getattr(viewer, "db_id", None)
    if role in _PRIVILEGED_ROLES:
        return

    hold: LegalHold | None = None
    if evidence.legal_hold_id is not None:
        hold = await session.get(LegalHold, evidence.legal_hold_id)
        if hold is not None and hold.ethical_wall:
            # 倫理壁が有効な Legal Hold に紐づく証拠は特権ロール以外は不可視。
            raise ForbiddenError("この証拠は Legal Hold の倫理壁により閲覧できません。")

    if evidence.contract_id is not None:
        contract = await session.get(Contract, evidence.contract_id)
        if await access_control.can_access(session, viewer=viewer, contract=contract):
            return
    elif evidence.matter_id is not None:
        matter = await session.get(LegalMatter, evidence.matter_id)
        if matter is not None and actor_id is not None and matter.assignee_id == actor_id:
            return
    else:
        if actor_id is not None and actor_id in (evidence.collected_by, evidence.created_by):
            return

    if hold is not None and actor_id is not None and hold.started_by == actor_id:
        return

    raise ForbiddenError("この証拠を閲覧する権限がありません。")


async def list_evidence(
    session: AsyncSession,
    *,
    matter_id: int | None = None,
    contract_id: int | None = None,
    relevance: str | None = None,
    is_duplicate: bool | None = None,
    source_type: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[Evidence], int]:
    stmt = select(Evidence).where(Evidence.deleted_at.is_(None))
    if matter_id is not None:
        stmt = stmt.where(Evidence.matter_id == matter_id)
    if contract_id is not None:
        stmt = stmt.where(Evidence.contract_id == contract_id)
    if relevance is not None:
        if relevance not in _ALLOWED_RELEVANCE:
            raise ValidationError(f"不正な関連性区分です: {relevance!r}")
        stmt = stmt.where(Evidence.relevance == relevance)
    if is_duplicate is not None:
        stmt = stmt.where(Evidence.is_duplicate == is_duplicate)
    if source_type is not None:
        if source_type not in _ALLOWED_SOURCE:
            raise ValidationError(f"不正な入手経路です: {source_type!r}")
        stmt = stmt.where(Evidence.source_type == source_type)
    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    stmt = stmt.order_by(Evidence.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def list_duplicates(session: AsyncSession, *, evidence_id: int) -> list[Evidence]:
    """指定証拠と同一ハッシュを持つ他の証拠を列挙する（#225）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    stmt = select(Evidence).where(
        Evidence.sha256_hash == evidence.sha256_hash,
        Evidence.id != evidence.id,
        Evidence.deleted_at.is_(None),
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_evidence(
    session: AsyncSession,
    *,
    actor_id: int | None,
    title: str,
    description: str | None = None,
    source_type: str = EvidenceSourceType.UPLOAD.value,
    matter_id: int | None = None,
    contract_id: int | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    storage: str = "local",
    storage_ref: str | None = None,
    file_content_base64: str | None = None,
    checksum_sha256: str | None = None,
    collected_by: int | None = None,
    collected_by_name: str | None = None,
    collected_at: datetime | None = None,
) -> Evidence:
    """証拠を登録する（#217 Evidence Repository・#218 採番・#219 ハッシュ）.

    ``file_content_base64``（小容量ファイル・写真等）または
    ``checksum_sha256``（クライアント側で事前計算済みの大容量ファイル。
    ``app.services.upload_service`` の既存フローと同様に実ファイルは外部
    ストレージへ別途アップロード済みである前提）のいずれかを必須とする。
    """
    if not title.strip():
        raise ValidationError("title は必須です。")
    if source_type not in _ALLOWED_SOURCE:
        raise ValidationError(f"不正な入手経路です: {source_type!r}")

    raw: bytes | None = None
    if file_content_base64:
        try:
            raw = base64.b64decode(file_content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationError("file_content_base64 のデコードに失敗しました。") from exc

    if raw is not None:
        sha256_hash = compute_sha256(raw)
        if checksum_sha256 and checksum_sha256.strip().lower() != sha256_hash:
            raise ValidationError(
                "checksum_sha256 が file_content_base64 の実体ハッシュと一致しません。"
            )
        size_bytes: int | None = len(raw)
        exif = extract_exif(raw) if (mime_type or "").startswith("image/") else None
    elif checksum_sha256:
        sha256_hash = checksum_sha256.strip().lower()
        if len(sha256_hash) != 64:
            raise ValidationError("checksum_sha256 は SHA-256（64 桁 16 進数）で指定してください。")
        size_bytes = None
        exif = None
    else:
        raise ValidationError("file_content_base64 または checksum_sha256 のいずれかが必要です。")

    if matter_id is not None and await session.get(LegalMatter, matter_id) is None:
        raise NotFoundError(f"法務案件が見つかりません（id={matter_id}）")
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")

    code = await _generate_evidence_code(session)
    relevance, relevance_score, relevance_note = classify_relevance(
        title=title, description=description
    )
    duplicate = await _find_duplicate(session, sha256_hash=sha256_hash)

    row = Evidence(
        evidence_code=code,
        matter_id=matter_id,
        contract_id=contract_id,
        title=title,
        description=description,
        source_type=source_type,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage=storage,
        storage_ref=storage_ref,
        sha256_hash=sha256_hash,
        is_duplicate=duplicate is not None,
        duplicate_of_id=duplicate.id if duplicate else None,
        exif_metadata=exif,
        relevance=relevance,
        relevance_score=relevance_score,
        relevance_note=relevance_note,
        collected_by=collected_by,
        collected_by_name=collected_by_name,
        collected_at=collected_at or datetime.now(UTC),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    await _append_custody_event(
        session,
        evidence_id=row.id,
        action=EvidenceCustodyAction.COLLECTED.value,
        actor_id=actor_id,
        actor_name=collected_by_name,
        to_custodian=collected_by_name or "legal-ops-evidence-repository",
        notes="証拠登録（初回収集記録）",
    )
    await audit_service.log(
        session,
        actor_id=actor_id,
        action="evidence.create",
        target_type=_TARGET_TYPE,
        target_id=row.id,
        payload={
            "evidence_code": row.evidence_code,
            "sha256_hash": row.sha256_hash,
            "is_duplicate": row.is_duplicate,
            "source_type": row.source_type,
        },
    )
    return row


# ---------------------------------------------------------------------------
# メール証拠取込（#226）
# ---------------------------------------------------------------------------


def _decode_email_part(message: Message) -> str:
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")
    fallback = message.get_payload()
    return fallback if isinstance(fallback, str) else ""


def _parse_eml(raw_eml: str) -> dict[str, Any]:
    msg = message_from_string(raw_eml)
    subject = msg.get("Subject", "") or "(件名なし)"
    date_header = msg.get("Date")
    sent_at: str | None = None
    if isinstance(date_header, str) and date_header.strip():
        try:
            sent_at = parsedate_to_datetime(date_header).isoformat()
        except (TypeError, ValueError):
            sent_at = None

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = _decode_email_part(part)
                break
    else:
        body = _decode_email_part(msg)

    return {
        "subject": subject,
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "message_id": msg.get("Message-ID", ""),
        "sent_at": sent_at,
        "body_preview": body[:2000],
    }


async def ingest_email_evidence(
    session: AsyncSession,
    *,
    actor_id: int | None,
    raw_eml: str,
    matter_id: int | None = None,
    contract_id: int | None = None,
    collected_by: int | None = None,
    collected_by_name: str | None = None,
) -> Evidence:
    """RFC 822（.eml）形式のメール本文を証拠として取り込む（#226）."""
    if not raw_eml.strip():
        raise ValidationError("メール本文（.eml）が空です。")

    parsed = _parse_eml(raw_eml)
    raw_bytes = raw_eml.encode("utf-8")
    sha256_hash = compute_sha256(raw_bytes)

    if matter_id is not None and await session.get(LegalMatter, matter_id) is None:
        raise NotFoundError(f"法務案件が見つかりません（id={matter_id}）")
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")

    code = await _generate_evidence_code(session)
    title = str(parsed["subject"]) or "(メール証拠)"
    relevance, relevance_score, relevance_note = classify_relevance(
        title=title, description=str(parsed["body_preview"])
    )
    duplicate = await _find_duplicate(session, sha256_hash=sha256_hash)
    email_metadata = {k: v for k, v in parsed.items() if k != "body_preview"}

    row = Evidence(
        evidence_code=code,
        matter_id=matter_id,
        contract_id=contract_id,
        title=title,
        description=str(parsed["body_preview"]) or None,
        source_type=EvidenceSourceType.EMAIL.value,
        filename=f"{code}.eml",
        mime_type="message/rfc822",
        size_bytes=len(raw_bytes),
        storage="local",
        storage_ref=None,
        sha256_hash=sha256_hash,
        is_duplicate=duplicate is not None,
        duplicate_of_id=duplicate.id if duplicate else None,
        email_metadata=email_metadata,
        relevance=relevance,
        relevance_score=relevance_score,
        relevance_note=relevance_note,
        collected_by=collected_by,
        collected_by_name=collected_by_name,
        collected_at=datetime.now(UTC),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    await _append_custody_event(
        session,
        evidence_id=row.id,
        action=EvidenceCustodyAction.COLLECTED.value,
        actor_id=actor_id,
        actor_name=collected_by_name,
        to_custodian=collected_by_name or "legal-ops-evidence-repository",
        notes="メール証拠取込（.eml）",
    )
    await audit_service.log(
        session,
        actor_id=actor_id,
        action="evidence.email_ingest",
        target_type=_TARGET_TYPE,
        target_id=row.id,
        payload={
            "evidence_code": row.evidence_code,
            "sha256_hash": row.sha256_hash,
            "subject": title,
        },
    )
    return row


# ---------------------------------------------------------------------------
# 閲覧履歴・タイムライン・Export（#222/#223/#224）
# ---------------------------------------------------------------------------


async def record_view(
    session: AsyncSession, *, evidence_id: int, viewer_id: int | None
) -> Evidence:
    """証拠の閲覧を監査ログへ記録する（#222 証拠閲覧履歴）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    await audit_service.log(
        session,
        actor_id=viewer_id,
        action="evidence.view",
        target_type=_TARGET_TYPE,
        target_id=evidence.id,
        payload={"evidence_code": evidence.evidence_code},
    )
    return evidence


async def get_view_history(
    session: AsyncSession, *, evidence_id: int, page: int = 1, size: int = 50
) -> tuple[list[AuditLog], int]:
    """証拠の閲覧・Export 履歴を監査ログ基盤から取得する（#222）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    stmt = select(AuditLog).where(
        AuditLog.target_type == _TARGET_TYPE,
        AuditLog.target_id == evidence.id,
        AuditLog.action.in_(_VIEW_ACTIONS),
    )
    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    stmt = stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def get_timeline(session: AsyncSession, *, evidence_id: int) -> list[dict[str, Any]]:
    """Chain of Custody と監査ログを時系列でマージした証拠タイムライン（#223）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    custody_rows = await list_custody_events(session, evidence_id=evidence.id)
    audit_rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.target_type == _TARGET_TYPE, AuditLog.target_id == evidence.id)
                .order_by(AuditLog.id.asc())
            )
        )
        .scalars()
        .all()
    )

    timeline: list[dict[str, Any]] = []
    for c in custody_rows:
        timeline.append(
            {
                "type": "custody",
                "occurred_at": c.occurred_at,
                "action": c.action,
                "actor_id": c.actor_id,
                "actor_name": c.actor_name,
                "from_custodian": c.from_custodian,
                "to_custodian": c.to_custodian,
                "notes": c.notes,
                "hash_chain": c.hash_chain,
            }
        )
    for a in audit_rows:
        timeline.append(
            {
                "type": "audit",
                "occurred_at": a.occurred_at,
                "action": a.action,
                "actor_id": a.actor_id,
                "actor_name": None,
                "from_custodian": None,
                "to_custodian": None,
                "notes": None,
                "hash_chain": a.hash_chain,
            }
        )
    timeline.sort(key=lambda item: item["occurred_at"])
    return timeline


async def export_evidence_bundle(
    session: AsyncSession, *, evidence_id: int, actor_id: int | None
) -> dict[str, Any]:
    """証拠のメタデータ・タイムライン・整合性検証結果を含むバンドルを出力する（#224）."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    timeline = await get_timeline(session, evidence_id=evidence.id)
    chain_ok = await verify_custody_chain(session, evidence_id=evidence.id)

    bundle: dict[str, Any] = {
        "evidence_code": evidence.evidence_code,
        "title": evidence.title,
        "description": evidence.description,
        "sha256_hash": evidence.sha256_hash,
        "source_type": evidence.source_type,
        "filename": evidence.filename,
        "mime_type": evidence.mime_type,
        "collected_at": evidence.collected_at.isoformat() if evidence.collected_at else None,
        "collected_by_name": evidence.collected_by_name,
        "relevance": evidence.relevance,
        "relevance_score": evidence.relevance_score,
        "relevance_note": evidence.relevance_note,
        "is_duplicate": evidence.is_duplicate,
        "duplicate_of_id": evidence.duplicate_of_id,
        "is_under_hold": evidence.is_under_hold,
        "exif_metadata": evidence.exif_metadata,
        "email_metadata": evidence.email_metadata,
        "custody_chain_verified": chain_ok,
        "timeline": [{**item, "occurred_at": item["occurred_at"].isoformat()} for item in timeline],
        "exported_at": datetime.now(UTC).isoformat(),
    }
    await audit_service.log(
        session,
        actor_id=actor_id,
        action="evidence.export",
        target_type=_TARGET_TYPE,
        target_id=evidence.id,
        payload={"evidence_code": evidence.evidence_code, "custody_chain_verified": chain_ok},
    )
    return bundle


# ---------------------------------------------------------------------------
# Legal Hold 紐付け・解除承認ワークフロー（#230）
# ---------------------------------------------------------------------------


async def link_legal_hold(
    session: AsyncSession, *, evidence_id: int, legal_hold_id: int, actor_id: int | None
) -> Evidence:
    """既存の Legal Hold（``app.models.access_control.LegalHold``）を証拠に紐付ける."""
    evidence = await get_evidence(session, evidence_id=evidence_id)
    hold = await session.get(LegalHold, legal_hold_id)
    if hold is None:
        raise NotFoundError(f"Legal Hold が見つかりません（id={legal_hold_id}）")

    evidence.legal_hold_id = hold.id
    evidence.is_under_hold = hold.status == "active"
    await session.flush()

    await _append_custody_event(
        session,
        evidence_id=evidence.id,
        action=EvidenceCustodyAction.HOLD_APPLIED.value,
        actor_id=actor_id,
        notes=f"Legal Hold #{hold.id} 紐付け",
    )
    await session.refresh(evidence)
    return evidence


async def request_hold_release(
    session: AsyncSession,
    *,
    legal_hold_id: int,
    requested_by: int | None,
    reason: str,
    evidence_id: int | None = None,
) -> EvidenceHoldReleaseApproval:
    """Legal Hold 解除申請を起票する（#230・決裁は :func:`decide_hold_release`）."""
    hold = await session.get(LegalHold, legal_hold_id)
    if hold is None:
        raise NotFoundError(f"Legal Hold が見つかりません（id={legal_hold_id}）")
    if hold.status != "active":
        raise ConflictError("解除申請できるのは active な Legal Hold のみです。")
    if not reason or not reason.strip():
        raise ValidationError("解除理由（reason）は必須です。")
    if evidence_id is not None:
        await get_evidence(session, evidence_id=evidence_id)

    pending = (
        await session.execute(
            select(EvidenceHoldReleaseApproval.id).where(
                EvidenceHoldReleaseApproval.legal_hold_id == legal_hold_id,
                EvidenceHoldReleaseApproval.status == EvidenceHoldApprovalStatus.PENDING.value,
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise ConflictError("この Legal Hold には既に決裁待ちの解除申請があります。")

    approval = EvidenceHoldReleaseApproval(
        legal_hold_id=legal_hold_id,
        evidence_id=evidence_id,
        requested_by=requested_by,
        reason=reason,
        status=EvidenceHoldApprovalStatus.PENDING.value,
    )
    session.add(approval)
    await session.flush()
    await session.refresh(approval)

    await audit_service.log(
        session,
        actor_id=requested_by,
        action="evidence.hold_release.request",
        target_type="legal_holds",
        target_id=legal_hold_id,
        payload={"reason": reason, "evidence_id": evidence_id, "approval_id": approval.id},
    )
    return approval


async def decide_hold_release(
    session: AsyncSession,
    *,
    approval_id: int,
    decided_by: int | None,
    approve: bool,
    decision_note: str | None = None,
) -> EvidenceHoldReleaseApproval:
    """Legal Hold 解除申請を決裁する。申請者本人による決裁は職務分掌違反として拒否する."""
    approval = await session.get(EvidenceHoldReleaseApproval, approval_id)
    if approval is None:
        raise NotFoundError(f"解除申請が見つかりません（id={approval_id}）")
    if approval.status != EvidenceHoldApprovalStatus.PENDING.value:
        raise ConflictError("既に決裁済みの申請です。")
    if (
        decided_by is not None
        and approval.requested_by is not None
        and decided_by == approval.requested_by
    ):
        raise ForbiddenError("職務分掌のため、申請者本人は同一の解除申請を決裁できません。")

    approval.status = (
        EvidenceHoldApprovalStatus.APPROVED.value
        if approve
        else EvidenceHoldApprovalStatus.REJECTED.value
    )
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(UTC)
    approval.decision_note = decision_note

    if approve:
        hold = await session.get(LegalHold, approval.legal_hold_id)
        if hold is None:
            raise NotFoundError(f"Legal Hold が見つかりません（id={approval.legal_hold_id}）")
        hold.status = "released"
        hold.released_at = approval.decided_at
        hold.released_by = decided_by
        hold.release_reason = decision_note or approval.reason

        if approval.evidence_id is not None:
            evidence = await get_evidence(session, evidence_id=approval.evidence_id)
            evidence.is_under_hold = False
            await _append_custody_event(
                session,
                evidence_id=evidence.id,
                action=EvidenceCustodyAction.HOLD_RELEASED.value,
                actor_id=decided_by,
                notes=decision_note or "Legal Hold 解除承認",
            )

        # hold.status は Hold 全体を released にするため、同一 legal_hold_id を
        # 参照する他の Evidence（上記で処理済みの approval.evidence_id を除く）
        # も is_under_hold=False へ揃える。放置すると解除済み Hold を指したまま
        # is_under_hold=True の証拠が残ってしまう。
        other_stmt = select(Evidence).where(
            Evidence.legal_hold_id == hold.id,
            Evidence.deleted_at.is_(None),
        )
        if approval.evidence_id is not None:
            other_stmt = other_stmt.where(Evidence.id != approval.evidence_id)
        other_rows = (await session.execute(other_stmt)).scalars().all()
        for other in other_rows:
            if not other.is_under_hold:
                continue
            other.is_under_hold = False
            await _append_custody_event(
                session,
                evidence_id=other.id,
                action=EvidenceCustodyAction.HOLD_RELEASED.value,
                actor_id=decided_by,
                notes=decision_note or "Legal Hold 解除承認（Hold 単位の一括解除）",
            )
        await audit_service.log(
            session,
            actor_id=decided_by,
            action="legal_hold.release",
            target_type="legal_holds",
            target_id=hold.id,
            payload={"reason": hold.release_reason, "approval_id": approval.id},
        )
    else:
        await audit_service.log(
            session,
            actor_id=decided_by,
            action="evidence.hold_release.reject",
            target_type="legal_holds",
            target_id=approval.legal_hold_id,
            payload={"approval_id": approval.id, "note": decision_note},
        )

    await session.flush()
    await session.refresh(approval)
    return approval


async def list_hold_release_approvals(
    session: AsyncSession,
    *,
    legal_hold_id: int | None = None,
    status: str | None = None,
) -> list[EvidenceHoldReleaseApproval]:
    stmt = select(EvidenceHoldReleaseApproval)
    if legal_hold_id is not None:
        stmt = stmt.where(EvidenceHoldReleaseApproval.legal_hold_id == legal_hold_id)
    if status is not None:
        stmt = stmt.where(EvidenceHoldReleaseApproval.status == status)
    stmt = stmt.order_by(EvidenceHoldReleaseApproval.id.desc())
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "add_custody_event",
    "classify_relevance",
    "compute_sha256",
    "create_evidence",
    "decide_hold_release",
    "ensure_evidence_visible",
    "export_evidence_bundle",
    "extract_exif",
    "get_evidence",
    "get_timeline",
    "get_view_history",
    "ingest_email_evidence",
    "link_legal_hold",
    "list_custody_events",
    "list_duplicates",
    "list_evidence",
    "list_hold_release_approvals",
    "record_view",
    "request_hold_release",
    "verify_custody_chain",
]
