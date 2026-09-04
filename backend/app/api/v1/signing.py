"""電子契約・電子署名エンベロープのエンドポイント（ロードマップ #1〜#4）.

- CRUD: 作成（draft）／一覧／詳細／証跡イベント一覧
- 状態遷移: send / consent / view / sign / complete / cancel
  （遷移規則は ``app.services.signing_service`` のルールエンジンに従う）
- 全遷移を監査ログ（hash chain）と追記専用イベントに記録する
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.signing import (
    SigningCancelIn,
    SigningCompleteIn,
    SigningConsentIn,
    SigningEnvelopeCreate,
    SigningEnvelopeOut,
    SigningEventOut,
    SigningSignIn,
)
from app.services import audit_service, signing_service

router = APIRouter(prefix="/signing", tags=["signing"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


@router.get(
    "",
    response_model=Page[SigningEnvelopeOut],
    summary="署名エンベロープ一覧",
)
async def list_envelopes(
    contract_id: int | None = None,
    status_: str | None = Query(default=None, alias="status"),
    page: int = 1,
    size: int = 20,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[SigningEnvelopeOut]:
    items, total = await signing_service.list_envelopes(
        session, contract_id=contract_id, status=status_, page=page, size=size
    )
    return Page[SigningEnvelopeOut](items=items, total=total, page=page, size=size)


@router.post(
    "",
    response_model=SigningEnvelopeOut,
    status_code=status.HTTP_201_CREATED,
    summary="署名エンベロープ作成（draft）",
)
async def create_envelope(
    body: SigningEnvelopeCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    envelope = await signing_service.create_envelope(
        session,
        actor_id=current_user.db_id,
        contract_id=body.contract_id,
        method=body.method.value if hasattr(body.method, "value") else str(body.method),
        provider=body.provider.value if hasattr(body.provider, "value") else str(body.provider),
        counterparty_name=body.counterparty_name,
        counterparty_email=body.counterparty_email,
        note=body.note,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="esignature.create",
        target_type="esignature_envelopes",
        target_id=envelope.id,
        request=request,
        payload={"envelope_no": envelope.envelope_no, "contract_id": envelope.contract_id},
    )
    return SigningEnvelopeOut.model_validate(envelope)


@router.get(
    "/{envelope_id}",
    response_model=SigningEnvelopeOut,
    summary="署名エンベロープ詳細",
)
async def get_envelope(
    envelope_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> SigningEnvelopeOut:
    envelope = await signing_service.get_envelope(session, envelope_id=envelope_id)
    return SigningEnvelopeOut.model_validate(envelope)


@router.get(
    "/{envelope_id}/events",
    response_model=list[SigningEventOut],
    summary="証跡イベント一覧（追記専用・読み取りのみ）",
)
async def list_events(
    envelope_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[SigningEventOut]:
    events = await signing_service.list_events(session, envelope_id=envelope_id)
    return [SigningEventOut.model_validate(e) for e in events]


async def _transition_and_audit(
    *,
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    envelope_id: int,
    action: str,
    call: Any,
) -> SigningEnvelopeOut:
    envelope = await call
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="esignature_envelopes",
        target_id=envelope.id,
        request=request,
        payload={"envelope_no": envelope.envelope_no, "status": envelope.status},
    )
    return SigningEnvelopeOut.model_validate(envelope)


@router.post(
    "/{envelope_id}/send",
    response_model=SigningEnvelopeOut,
    summary="相手方へ署名依頼を送信（draft → sent）",
)
async def send_envelope(
    envelope_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.send",
        call=signing_service.send_envelope(
            session, envelope_id=envelope_id, actor_id=current_user.db_id
        ),
    )


@router.post(
    "/{envelope_id}/consent",
    response_model=SigningEnvelopeOut,
    summary="相手方の承諾証跡を記録（建設業法 19 条・電磁的方法）",
)
async def record_consent(
    envelope_id: int,
    body: SigningConsentIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.consent",
        call=signing_service.record_consent(
            session,
            envelope_id=envelope_id,
            actor_id=current_user.db_id,
            consentor_name=body.consentor_name,
            consentor_email=body.consentor_email,
            consent_note=body.note,
        ),
    )


@router.post(
    "/{envelope_id}/view",
    response_model=SigningEnvelopeOut,
    summary="相手方の閲覧を記録（sent → viewed）",
)
async def mark_viewed(
    envelope_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.view",
        call=signing_service.mark_viewed(
            session, envelope_id=envelope_id, actor_id=current_user.db_id
        ),
    )


@router.post(
    "/{envelope_id}/sign",
    response_model=SigningEnvelopeOut,
    summary="相手方の署名を受領（sent/viewed → signed）",
)
async def sign_envelope(
    envelope_id: int,
    body: SigningSignIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.sign",
        call=signing_service.sign_envelope(
            session,
            envelope_id=envelope_id,
            actor_id=current_user.db_id,
            signer_name=body.signer_name,
            signer_email=body.signer_email,
        ),
    )


@router.post(
    "/{envelope_id}/complete",
    response_model=SigningEnvelopeOut,
    summary="締結完了（signed → completed・正本取込任意）",
)
async def complete_envelope(
    envelope_id: int,
    body: SigningCompleteIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.complete",
        call=signing_service.complete_envelope(
            session,
            envelope_id=envelope_id,
            actor_id=current_user.db_id,
            attachment_id=body.attachment_id,
        ),
    )


@router.post(
    "/{envelope_id}/cancel",
    response_model=SigningEnvelopeOut,
    summary="エンベロープ取消（draft/sent/viewed → cancelled）",
)
async def cancel_envelope(
    envelope_id: int,
    body: SigningCancelIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> SigningEnvelopeOut:
    return await _transition_and_audit(
        session=session,
        request=request,
        current_user=current_user,
        envelope_id=envelope_id,
        action="esignature.cancel",
        call=signing_service.cancel_envelope(
            session,
            envelope_id=envelope_id,
            actor_id=current_user.db_id,
            reason=body.reason,
        ),
    )
