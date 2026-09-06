"""独禁法・入札談合コンプライアンスエンドポイント（Issue #122・ロードマップ #113〜#124）.

.. note::
   このルーターは統合担当（コーディネーター）が ``app/api/v1/__init__.py`` へ
   ``from app.api.v1.antitrust import router as antitrust_router`` の import と
   ``api_router.include_router(antitrust_router)`` を追加するまで、
   アプリケーション本体には登録されない（衝突回避のため本 Issue の実装では
   共有ファイルを編集しない）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.antitrust_compliance import (
    AntitrustApplicationCancel,
    AntitrustApplicationComplete,
    AntitrustApplicationCreate,
    AntitrustApplicationDecision,
    AntitrustApplicationOut,
    AntitrustCheckCreate,
    AntitrustCheckOut,
    AntitrustConsultationCreate,
    AntitrustConsultationOut,
    ComplianceTrainingCreate,
    ComplianceTrainingOut,
)
from app.schemas.common import Page
from app.services import antitrust_service, audit_service

router = APIRouter(prefix="/antitrust", tags=["antitrust"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")
_APPROVE_ROLES = ("reviewer", "approver", "admin")


# ---------------------------------------------------------------------------
# #113/#114/#117/#118/#119 決定論的ルールベースチェック
# ---------------------------------------------------------------------------


@router.get(
    "/checks",
    response_model=Page[AntitrustCheckOut],
    summary="独禁法・入札談合等チェック結果一覧（#113/#114/#117/#118/#119）",
)
async def list_checks(
    check_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    contract_id: int | None = Query(default=None),
    jv_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[AntitrustCheckOut]:
    items, total = await antitrust_service.list_checks(
        session,
        check_type=check_type,
        severity=severity,
        contract_id=contract_id,
        jv_id=jv_id,
        page=page,
        size=size,
    )
    return Page[AntitrustCheckOut](
        items=[AntitrustCheckOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/checks/{check_id}",
    response_model=AntitrustCheckOut,
    summary="チェック結果の詳細取得",
)
async def get_check(
    check_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> AntitrustCheckOut:
    try:
        row = await antitrust_service.get_check(session, check_id=check_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AntitrustCheckOut.model_validate(row)


@router.post(
    "/checks",
    response_model=AntitrustCheckOut,
    status_code=status.HTTP_201_CREATED,
    summary="チェックを実行（決定論的ルールベース・AI 不使用）",
)
async def run_check(
    body: AntitrustCheckCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> AntitrustCheckOut:
    try:
        row = await antitrust_service.create_check(
            session,
            actor_id=current_user.db_id,
            check_type=body.check_type,
            subject=body.subject,
            context=body.context,
            contract_id=body.contract_id,
            jv_id=body.jv_id,
            notes=body.notes,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_check.run",
        target_type="antitrust_checks",
        target_id=row.id,
        request=request,
        payload={"check_type": row.check_type, "severity": row.severity},
    )
    return AntitrustCheckOut.model_validate(row)


# ---------------------------------------------------------------------------
# #115/#116/#121/#122/#123 事前申請 → 承認 → 記録
# ---------------------------------------------------------------------------


@router.get(
    "/applications",
    response_model=Page[AntitrustApplicationOut],
    summary="事前申請一覧（競合接触/会合懇親会/接待/公務員接触/寄付協賛）",
)
async def list_applications(
    application_type: str | None = Query(default=None, alias="type"),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[AntitrustApplicationOut]:
    try:
        items, total = await antitrust_service.list_applications(
            session,
            application_type=application_type,
            status=status_,
            page=page,
            size=size,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return Page[AntitrustApplicationOut](
        items=[AntitrustApplicationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/applications/{application_id}",
    response_model=AntitrustApplicationOut,
    summary="事前申請の詳細取得",
)
async def get_application(
    application_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> AntitrustApplicationOut:
    try:
        row = await antitrust_service.get_application(session, application_id=application_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AntitrustApplicationOut.model_validate(row)


@router.post(
    "/applications",
    response_model=AntitrustApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="事前申請を登録（submitted）",
)
async def create_application(
    body: AntitrustApplicationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> AntitrustApplicationOut:
    try:
        row = await antitrust_service.create_application(
            session,
            actor_id=current_user.db_id,
            application_type=body.application_type,
            title=body.title,
            counterparty_name=body.counterparty_name,
            counterparty_organization=body.counterparty_organization,
            purpose=body.purpose,
            scheduled_at=body.scheduled_at,
            location=body.location,
            amount_jpy=body.amount_jpy,
            attendees=body.attendees,
            contract_id=body.contract_id,
            jv_id=body.jv_id,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_application.create",
        target_type="antitrust_prior_applications",
        target_id=row.id,
        request=request,
        payload={"application_type": row.application_type},
    )
    return AntitrustApplicationOut.model_validate(row)


@router.post(
    "/applications/{application_id}/decision",
    response_model=AntitrustApplicationOut,
    summary="事前申請の承認・却下（submitted → approved/rejected）",
)
async def decide_application(
    application_id: int,
    body: AntitrustApplicationDecision,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_APPROVE_ROLES)),
) -> AntitrustApplicationOut:
    try:
        row = await antitrust_service.decide_application(
            session,
            application_id=application_id,
            actor_id=current_user.db_id,
            decision=body.decision,
            decision_note=body.decision_note,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_application.decide",
        target_type="antitrust_prior_applications",
        target_id=row.id,
        request=request,
        payload={"status": row.status},
    )
    return AntitrustApplicationOut.model_validate(row)


@router.post(
    "/applications/{application_id}/complete",
    response_model=AntitrustApplicationOut,
    summary="実施記録の登録（approved → completed）",
)
async def complete_application(
    application_id: int,
    body: AntitrustApplicationComplete,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> AntitrustApplicationOut:
    try:
        row = await antitrust_service.complete_application(
            session,
            application_id=application_id,
            actor_id=current_user.db_id,
            outcome_note=body.outcome_note,
            occurred_at=body.occurred_at,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_application.complete",
        target_type="antitrust_prior_applications",
        target_id=row.id,
        request=request,
        payload={"status": row.status},
    )
    return AntitrustApplicationOut.model_validate(row)


@router.post(
    "/applications/{application_id}/cancel",
    response_model=AntitrustApplicationOut,
    summary="事前申請の取下げ（submitted/approved → cancelled）",
)
async def cancel_application(
    application_id: int,
    body: AntitrustApplicationCancel,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> AntitrustApplicationOut:
    try:
        row = await antitrust_service.cancel_application(
            session,
            application_id=application_id,
            actor_id=current_user.db_id,
            cancel_reason=body.cancel_reason,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_application.cancel",
        target_type="antitrust_prior_applications",
        target_id=row.id,
        request=request,
        payload={"status": row.status},
    )
    return AntitrustApplicationOut.model_validate(row)


# ---------------------------------------------------------------------------
# #120 競争法 AI 相談
# ---------------------------------------------------------------------------


@router.get(
    "/consultations",
    response_model=Page[AntitrustConsultationOut],
    summary="競争法 AI 相談の履歴一覧（#120）",
)
async def list_consultations(
    contract_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[AntitrustConsultationOut]:
    items, total = await antitrust_service.list_consultations(
        session, contract_id=contract_id, page=page, size=size
    )
    return Page[AntitrustConsultationOut](
        items=[AntitrustConsultationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/consultations",
    response_model=AntitrustConsultationOut,
    status_code=status.HTTP_201_CREATED,
    summary="競争法 AI 相談（一次情報引用付きの参考回答・#120）",
)
async def create_consultation(
    body: AntitrustConsultationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> AntitrustConsultationOut:
    try:
        row = await antitrust_service.create_consultation(
            session,
            actor_id=current_user.db_id,
            query_text=body.query_text,
            contract_id=body.contract_id,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="antitrust_consultation.create",
        target_type="antitrust_consultations",
        target_id=row.id,
        request=request,
        payload={"contract_id": row.contract_id},
    )
    return AntitrustConsultationOut.model_validate(row)


# ---------------------------------------------------------------------------
# #124 コンプライアンス研修履歴
# ---------------------------------------------------------------------------


@router.get(
    "/trainings",
    response_model=Page[ComplianceTrainingOut],
    summary="コンプライアンス研修履歴一覧（#124）",
)
async def list_trainings(
    user_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[ComplianceTrainingOut]:
    items, total = await antitrust_service.list_trainings(
        session, user_id=user_id, category=category, page=page, size=size
    )
    return Page[ComplianceTrainingOut](
        items=[ComplianceTrainingOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/trainings",
    response_model=ComplianceTrainingOut,
    status_code=status.HTTP_201_CREATED,
    summary="コンプライアンス研修履歴を登録（#124）",
)
async def create_training(
    body: ComplianceTrainingCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ComplianceTrainingOut:
    try:
        row = await antitrust_service.create_training(
            session,
            actor_id=current_user.db_id,
            training_title=body.training_title,
            completed_at=body.completed_at,
            user_id=body.user_id,
            attendee_name=body.attendee_name,
            category=body.category,
            score=body.score,
            certificate_url=body.certificate_url,
            notes=body.notes,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="compliance_training.create",
        target_type="compliance_trainings",
        target_id=row.id,
        request=request,
        payload={"category": row.category},
    )
    return ComplianceTrainingOut.model_validate(row)
