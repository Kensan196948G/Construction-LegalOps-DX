"""電子契約・電子署名エンベロープの業務サービス.

ロードマップ #1（電子契約連携）〜#4（締結済み正本取込）のうち、状態機械と
証跡（承諾を含む）を司る。ルールエンジン方針（§3.2）に従い、**AI を介さない
決定論的な遷移判定**を行う:

    draft → sent → viewed → signed → completed
    draft / sent / viewed → cancelled

``electronic`` 方式（建設業法 19 条）では、署名前に相手方の承諾
（``consent_received`` イベントと ``consent_*`` 列）が必須。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.attachment import Attachment
from app.models.contract_document import ContractDocument
from app.models.enums import SigningMethod, SigningProviderId, SigningStatus
from app.models.signing import ESignatureEnvelope, ESignatureEvent
from app.services.signing_provider import get_provider

logger = structlog.get_logger(__name__)

# --- 状態遷移行列（ルールエンジン・単一の正） -------------------------------
_ALLOWED_FROM: dict[str, set[str]] = {
    SigningStatus.SENT.value: {SigningStatus.DRAFT.value},
    SigningStatus.VIEWED.value: {SigningStatus.SENT.value},
    SigningStatus.SIGNED.value: {SigningStatus.SENT.value, SigningStatus.VIEWED.value},
    SigningStatus.COMPLETED.value: {SigningStatus.SIGNED.value},
    SigningStatus.CANCELLED.value: {
        SigningStatus.DRAFT.value,
        SigningStatus.SENT.value,
        SigningStatus.VIEWED.value,
    },
}

# 承諾記録を許可する状態（電磁的方法の承諾は「署名前」まで。draft/sent/viewed）
_CONSENT_ALLOWED_STATUSES = frozenset(
    {
        SigningStatus.DRAFT.value,
        SigningStatus.SENT.value,
        SigningStatus.VIEWED.value,
    }
)

# 締結プロセス（外観）用の sign 許可状態
_SIGN_ALLOWED_STATUSES = frozenset(
    {SigningStatus.SENT.value, SigningStatus.VIEWED.value}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _coerce_status(value: str) -> str:
    try:
        return SigningStatus(value).value
    except ValueError as exc:
        raise ValidationError(f"不正な署名ステータス: {value!r}") from exc


async def _fetch_envelope(session: AsyncSession, *, envelope_id: int) -> ESignatureEnvelope:
    envelope = await session.get(ESignatureEnvelope, envelope_id)
    if envelope is None:
        raise NotFoundError(f"esignature envelope {envelope_id} not found")
    return envelope


async def _append_event(
    session: AsyncSession,
    *,
    envelope: ESignatureEnvelope,
    event_type: str,
    actor_id: int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    """追記専用の証跡イベントを追加する（UPDATE / DELETE API は公開しない）."""
    session.add(
        ESignatureEvent(
            envelope_id=envelope.id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
        )
    )


def _check_transition(envelope: ESignatureEnvelope, *, target: str) -> None:
    allowed = _ALLOWED_FROM[target]
    if envelope.status not in allowed:
        raise ConflictError(
            f"署名ステータス遷移不可: {envelope.status!r} -> {target!r}"
            f"（許可元: {sorted(allowed)}）"
        )


async def create_envelope(
    session: AsyncSession,
    *,
    actor_id: int | None,
    contract_id: int,
    method: str,
    provider: str,
    counterparty_name: str | None = None,
    counterparty_email: str | None = None,
    note: str | None = None,
) -> ESignatureEnvelope:
    """署名エンベロープをドラフト作成する.

    demo / manual はそのまま作成できる。cloudsign / docusign は資格情報が
    未設定なら :class:`SigningProviderUnavailable`（503）で fail-closed する。
    """
    try:
        method_value = SigningMethod(method).value
    except ValueError as exc:
        raise ValidationError(f"不正な締結方法: {method!r}") from exc
    try:
        provider_value = SigningProviderId(provider).value
    except ValueError as exc:
        raise ValidationError(f"不正な署名プロバイダ: {provider!r}") from exc

    adapter = get_provider(provider_value)
    adapter.validate_config()

    envelope = ESignatureEnvelope(
        contract_id=contract_id,
        envelope_no="",  # flush 後に採番（ES-<id>）
        status=SigningStatus.DRAFT.value,
        method=method_value,
        provider=provider_value,
        counterparty_name=counterparty_name,
        counterparty_email=counterparty_email,
        note=note,
        created_by=actor_id,
        updated_by=actor_id,
        version=1,
    )
    session.add(envelope)
    await session.flush()

    external_ref = f"ES-ext-{uuid.uuid4().hex[:12].upper()}"
    external_id = await adapter.create_envelope(
        provider_envelope_id=external_ref, counterparty_email=counterparty_email
    )
    envelope.provider_envelope_id = external_id
    envelope.envelope_no = f"ES-{envelope.id:08d}"

    await _append_event(
        session,
        envelope=envelope,
        event_type="created",
        actor_id=actor_id,
        payload={
            "method": envelope.method,
            "provider": envelope.provider,
            "provider_envelope_id": external_id,
            "contract_id": contract_id,
        },
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def get_envelope(session: AsyncSession, *, envelope_id: int) -> ESignatureEnvelope:
    return await _fetch_envelope(session, envelope_id=envelope_id)


async def list_envelopes(
    session: AsyncSession,
    *,
    contract_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ESignatureEnvelope], int]:
    stmt = select(ESignatureEnvelope)
    if contract_id is not None:
        stmt = stmt.where(ESignatureEnvelope.contract_id == contract_id)
    if status is not None:
        stmt = stmt.where(ESignatureEnvelope.status == _coerce_status(status))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(ESignatureEnvelope.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), int(total)


async def list_events(
    session: AsyncSession, *, envelope_id: int
) -> list[ESignatureEvent]:
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    stmt = (
        select(ESignatureEvent)
        .where(ESignatureEvent.envelope_id == envelope.id)
        .order_by(ESignatureEvent.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def send_envelope(
    session: AsyncSession, *, envelope_id: int, actor_id: int | None
) -> ESignatureEnvelope:
    """相手方へ署名依頼を送信する（draft → sent）."""
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    _check_transition(envelope, target=SigningStatus.SENT.value)
    adapter = get_provider(envelope.provider)
    if envelope.provider_envelope_id:
        await adapter.send(provider_envelope_id=envelope.provider_envelope_id)
    envelope.status = SigningStatus.SENT.value
    envelope.sent_at = _now()
    envelope.updated_by = actor_id
    await _append_event(
        session, envelope=envelope, event_type="sent", actor_id=actor_id
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def record_consent(
    session: AsyncSession,
    *,
    envelope_id: int,
    actor_id: int | None,
    consentor_name: str | None = None,
    consentor_email: str | None = None,
    consent_note: str | None = None,
) -> ESignatureEnvelope:
    """相手方の承諾証跡を記録する（建設業法 19 条・電磁的方法による交付の承諾）."""
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    if envelope.status not in _CONSENT_ALLOWED_STATUSES:
        raise ConflictError(
            f"承諾の記録は署名前（draft/sent/viewed）のみ可能（現在: {envelope.status!r}）"
        )
    if envelope.method != SigningMethod.ELECTRONIC.value:
        raise ValidationError("承諾の記録は electronic 方式のみ対象です。")
    envelope.consent_confirmed_at = _now()
    envelope.consentor_name = consentor_name
    envelope.consentor_email = consentor_email
    envelope.consent_note = consent_note
    envelope.updated_by = actor_id
    await _append_event(
        session,
        envelope=envelope,
        event_type="consent_received",
        actor_id=actor_id,
        payload={"consentor_name": consentor_name, "note": consent_note},
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def mark_viewed(
    session: AsyncSession, *, envelope_id: int, actor_id: int | None
) -> ESignatureEnvelope:
    """相手方が閲覧したことを記録する（sent → viewed）."""
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    _check_transition(envelope, target=SigningStatus.VIEWED.value)
    envelope.status = SigningStatus.VIEWED.value
    envelope.viewed_at = _now()
    envelope.updated_by = actor_id
    await _append_event(
        session, envelope=envelope, event_type="viewed", actor_id=actor_id
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def sign_envelope(
    session: AsyncSession,
    *,
    envelope_id: int,
    actor_id: int | None,
    signer_name: str | None = None,
    signer_email: str | None = None,
) -> ESignatureEnvelope:
    """相手方の署名を受け付ける（sent/viewed → signed）.

    electronic 方式では事前の承諾記録（consent_confirmed_at）が必須。
    """
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    if envelope.status not in _SIGN_ALLOWED_STATUSES:
        raise ConflictError(
            f"署名は sent/viewed のみ可能（現在: {envelope.status!r}）"
        )
    if (
        envelope.method == SigningMethod.ELECTRONIC.value
        and envelope.consent_confirmed_at is None
    ):
        raise ValidationError(
            "electronic 方式では署名前に相手方の承諾記録（POST /signing/{id}/consent）"
            "が必要です（建設業法 19 条・電磁的方法の相手方承諾）。"
        )
    envelope.status = SigningStatus.SIGNED.value
    envelope.signed_at = _now()
    envelope.signer_name = signer_name
    envelope.signer_email = signer_email
    envelope.updated_by = actor_id
    await _append_event(
        session,
        envelope=envelope,
        event_type="signed",
        actor_id=actor_id,
        payload={"signer_name": signer_name, "signer_email": signer_email},
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def complete_envelope(
    session: AsyncSession,
    *,
    envelope_id: int,
    actor_id: int | None,
    attachment_id: int | None = None,
) -> ESignatureEnvelope:
    """締結（signed → completed）.

    ``attachment_id`` が指定された場合は締結済み原本
    （``contract_documents.doc_type='signed_original'``）として正本保管へ取り込む
    （ロードマップ #4 締結済み文書自動取込の API 境界）。
    """
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    _check_transition(envelope, target=SigningStatus.COMPLETED.value)

    signed_document_id: int | None = None
    if attachment_id is not None:
        attachment = await session.get(Attachment, attachment_id)
        if attachment is None:
            raise NotFoundError(f"attachment {attachment_id} not found")
        # 同一原本の再取込は冪等にする（既存ドキュメントがあれば再利用）
        existing = (
            await session.execute(
                select(ContractDocument).where(
                    ContractDocument.contract_id == envelope.contract_id,
                    ContractDocument.doc_type == "signed_original",
                    ContractDocument.source_attachment_id == attachment.id,
                )
            )
        ).scalars().first()
        if existing is not None:
            signed_document_id = existing.id
        else:
            document = ContractDocument(
                contract_id=envelope.contract_id,
                doc_type="signed_original",
                title=f"{attachment.filename}（電子締結原本）",
                priority=90,
                source_attachment_id=attachment.id,
                version=1,
            )
            session.add(document)
            await session.flush()
            signed_document_id = document.id

        envelope.signed_attachment_id = attachment.id
        envelope.signed_document_id = signed_document_id

    envelope.status = SigningStatus.COMPLETED.value
    envelope.completed_at = _now()
    envelope.updated_by = actor_id
    await _append_event(
        session,
        envelope=envelope,
        event_type="completed",
        actor_id=actor_id,
        payload={"signed_document_id": signed_document_id},
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


async def cancel_envelope(
    session: AsyncSession,
    *,
    envelope_id: int,
    actor_id: int | None,
    reason: str | None = None,
) -> ESignatureEnvelope:
    """エンベロープを取消す（draft/sent/viewed → cancelled）."""
    envelope = await _fetch_envelope(session, envelope_id=envelope_id)
    _check_transition(envelope, target=SigningStatus.CANCELLED.value)
    envelope.status = SigningStatus.CANCELLED.value
    envelope.updated_by = actor_id
    await _append_event(
        session,
        envelope=envelope,
        event_type="cancelled",
        actor_id=actor_id,
        payload={"reason": reason},
    )
    await session.flush()
    await session.refresh(envelope)
    return envelope


__all__ = [
    "cancel_envelope",
    "complete_envelope",
    "create_envelope",
    "get_envelope",
    "list_envelopes",
    "list_events",
    "mark_viewed",
    "record_consent",
    "send_envelope",
    "sign_envelope",
]
