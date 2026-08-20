"""知財管理・競合ウォッチ・審査書類の API.

- ``/ip-assets`` — 知財台帳（CRUD + 同期 + 書類）
- ``/ip-watch-targets`` / ``/ip-watch-events`` — 競合出願ウォッチ
- ``/ip-documents`` — 審査書類の収集・AI 解析
- ``/ip-dashboard`` — サマリ
- ``/ip/jpo-status`` — JPO API 接続状態

設計: docs/architecture/ip_management_design.md
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models.ip_asset import IpAsset
from app.models.ip_document import IpDocument
from app.models.ip_watch import IpWatchEvent, IpWatchTarget
from app.schemas.common import Page
from app.schemas.ip import (
    IpAssetCreate,
    IpAssetOut,
    IpAssetSyncResult,
    IpAssetUpdate,
    IpDashboardOut,
    IpDocumentAnalyzeResult,
    IpDocumentFetchRequest,
    IpDocumentFetchResult,
    IpDocumentOut,
    IpWatchEventOut,
    IpWatchTargetCreate,
    IpWatchTargetOut,
    IpWatchTargetSyncResult,
    IpWatchTargetUpdate,
    JpoStatusOut,
)
from app.services import ip_service

router = APIRouter(tags=["ip"])

_WRITE_ROLE = require_role("drafter", "reviewer", "approver", "admin")


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


async def _get_asset(
    session: AsyncSession,
    asset_id: int,
) -> IpAsset:
    asset = await session.get(IpAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ip asset not found")
    return asset


async def _get_watch_target(
    session: AsyncSession,
    target_id: int,
) -> IpWatchTarget:
    target = await session.get(IpWatchTarget, target_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watch target not found")
    return target


async def _get_document(
    session: AsyncSession,
    document_id: int,
) -> IpDocument:
    doc = await session.get(IpDocument, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ip document not found")
    return doc


def _to_watch_target_out(target: IpWatchTarget, asset_count: int, unread: int) -> IpWatchTargetOut:
    return IpWatchTargetOut(
        id=target.id,
        name=target.name,
        applicant_code=target.applicant_code,
        ip_types=list(target.ip_types or ["patent"]),
        status=target.status,
        notes=target.notes,
        asset_count=asset_count,
        unread_event_count=unread,
        created_at=target.created_at,
        updated_at=target.updated_at,
        deleted_at=target.deleted_at,
    )


# ---------------------------------------------------------------------------
# 知財台帳
# ---------------------------------------------------------------------------

ip_assets_router = APIRouter(prefix="/ip-assets", tags=["ip"])


@ip_assets_router.get(
    "",
    response_model=Page[IpAssetOut],
    summary="知財台帳一覧",
)
async def list_ip_assets(
    q: str | None = Query(default=None, description="出願番号/発明名称の部分一致"),
    ip_type: str | None = Query(default=None, description="patent/design/trademark"),
    status_: str | None = Query(default=None, alias="status"),
    watch_target_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[IpAssetOut]:
    stmt = select(IpAsset).where(IpAsset.deleted_at.is_(None))
    if q:
        stmt = stmt.where(
            IpAsset.application_number.ilike(f"%{q}%") | IpAsset.invention_title.ilike(f"%{q}%")
        )
    if ip_type:
        stmt = stmt.where(IpAsset.ip_type == ip_type)
    if status_:
        stmt = stmt.where(IpAsset.status == status_)
    if watch_target_id is not None:
        stmt = stmt.where(IpAsset.watch_target_id == watch_target_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(IpAsset.updated_at.desc()).offset((page - 1) * size).limit(size)
    rows = list((await session.execute(stmt)).scalars().all())
    return Page[IpAssetOut](
        items=[IpAssetOut.model_validate(a) for a in rows],
        total=total,
        page=page,
        size=size,
    )


@ip_assets_router.post(
    "",
    response_model=IpAssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="出願登録（JPO API から初期情報取得）",
)
async def create_ip_asset(
    payload: IpAssetCreate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpAssetOut:
    try:
        asset = await ip_service.register_asset(
            session,
            application_number=payload.application_number,
            ip_type=payload.ip_type,
            watch_target_id=payload.watch_target_id,
            notes=payload.notes,
            actor_id=current_user.db_id,
        )
    except ip_service.IpServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ip_service.JpoQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    await session.commit()
    return IpAssetOut.model_validate(asset)


@ip_assets_router.get(
    "/{asset_id}",
    response_model=IpAssetOut,
    summary="出願詳細",
)
async def get_ip_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> IpAssetOut:
    asset = await _get_asset(session, asset_id)
    return IpAssetOut.model_validate(asset)


@ip_assets_router.patch(
    "/{asset_id}",
    response_model=IpAssetOut,
    summary="出願情報の更新（メモ等）",
)
async def update_ip_asset(
    asset_id: int,
    payload: IpAssetUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpAssetOut:
    asset = await _get_asset(session, asset_id)
    if payload.notes is not None:
        asset.notes = payload.notes
    if payload.watch_target_id is not None:
        asset.watch_target_id = payload.watch_target_id
    asset.updated_by = current_user.db_id
    await session.commit()
    await session.refresh(asset)
    return IpAssetOut.model_validate(asset)


@ip_assets_router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="出願の論理削除",
)
async def delete_ip_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> None:
    asset = await _get_asset(session, asset_id)
    from datetime import UTC, datetime

    asset.deleted_at = datetime.now(UTC)
    asset.updated_by = current_user.db_id
    await session.commit()


@ip_assets_router.post(
    "/{asset_id}/sync",
    response_model=IpAssetSyncResult,
    summary="JPO API から経過情報を再取得",
)
async def sync_ip_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpAssetSyncResult:
    asset = await _get_asset(session, asset_id)
    try:
        calls, events = await ip_service.sync_asset(
            session,
            asset=asset,
            create_events=True,
        )
    except ip_service.JpoQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except ip_service.IpServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    await session.commit()
    return IpAssetSyncResult(
        asset_id=asset.id,
        application_number=asset.application_number,
        api_calls=calls,
        events_created=events,
        updated=True,
        message="経過情報を更新しました",
    )


@ip_assets_router.get(
    "/{asset_id}/documents",
    response_model=list[IpDocumentOut],
    summary="出願に紐づく審査書類一覧",
)
async def list_asset_documents(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[IpDocumentOut]:
    await _get_asset(session, asset_id)
    rows = list(
        (
            await session.execute(
                select(IpDocument)
                .where(
                    IpDocument.ip_asset_id == asset_id,
                    IpDocument.deleted_at.is_(None),
                )
                .order_by(IpDocument.fetched_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [IpDocumentOut.model_validate(d) for d in rows]


@ip_assets_router.post(
    "/{asset_id}/documents/fetch",
    response_model=IpDocumentFetchResult,
    summary="審査書類を JPO API から収集",
)
async def fetch_asset_documents(
    asset_id: int,
    payload: IpDocumentFetchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpDocumentFetchResult:
    asset = await _get_asset(session, asset_id)
    try:
        created, errors = await ip_service.fetch_documents(
            session,
            asset=asset,
            doc_types=list(payload.doc_types),
        )
    except ip_service.IpServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    await session.commit()
    return IpDocumentFetchResult(
        asset_id=asset.id,
        application_number=asset.application_number,
        fetched=[{"doc_type": d.doc_type, "doc_name": d.doc_name or ""} for d in created],
        errors=[{"doc_type": e, "message": e} for e in errors],
    )


# ---------------------------------------------------------------------------
# 競合ウォッチ
# ---------------------------------------------------------------------------

ip_watch_targets_router = APIRouter(prefix="/ip-watch-targets", tags=["ip-watch"])


@ip_watch_targets_router.get(
    "",
    response_model=Page[IpWatchTargetOut],
    summary="ウォッチ対象一覧",
)
async def list_watch_targets(
    q: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[IpWatchTargetOut]:
    stmt = select(IpWatchTarget).where(IpWatchTarget.deleted_at.is_(None))
    if q:
        stmt = stmt.where(IpWatchTarget.name.ilike(f"%{q}%"))
    if status_:
        stmt = stmt.where(IpWatchTarget.status == status_)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    rows = list(
        (
            await session.execute(
                stmt.order_by(IpWatchTarget.updated_at.desc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )

    items: list[IpWatchTargetOut] = []
    for target in rows:
        asset_count = (
            await session.execute(
                select(func.count())
                .select_from(IpAsset)
                .where(
                    IpAsset.watch_target_id == target.id,
                    IpAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        unread = (
            await session.execute(
                select(func.count())
                .select_from(IpWatchEvent)
                .where(
                    IpWatchEvent.watch_target_id == target.id,
                    IpWatchEvent.is_read.is_(False),
                    IpWatchEvent.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        items.append(_to_watch_target_out(target, asset_count, unread))
    return Page[IpWatchTargetOut](items=items, total=total, page=page, size=size)


@ip_watch_targets_router.post(
    "",
    response_model=IpWatchTargetOut,
    status_code=status.HTTP_201_CREATED,
    summary="ウォッチ対象の登録",
)
async def create_watch_target(
    payload: IpWatchTargetCreate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpWatchTargetOut:
    existing = (
        await session.execute(
            select(IpWatchTarget).where(
                IpWatchTarget.name == payload.name,
                IpWatchTarget.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同名のウォッチ対象が既に登録されています",
        )
    target = IpWatchTarget(
        name=payload.name,
        applicant_code=payload.applicant_code,
        ip_types=list(payload.ip_types or ["patent"]),
        status=payload.status,
        notes=payload.notes,
        created_by=current_user.db_id,
        updated_by=current_user.db_id,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return _to_watch_target_out(target, 0, 0)


@ip_watch_targets_router.patch(
    "/{target_id}",
    response_model=IpWatchTargetOut,
    summary="ウォッチ対象の更新",
)
async def update_watch_target(
    target_id: int,
    payload: IpWatchTargetUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpWatchTargetOut:
    target = await _get_watch_target(session, target_id)
    if payload.name is not None:
        target.name = payload.name
    if payload.applicant_code is not None:
        target.applicant_code = payload.applicant_code
    if payload.ip_types is not None:
        target.ip_types = list(payload.ip_types)
    if payload.status is not None:
        target.status = payload.status
    if payload.notes is not None:
        target.notes = payload.notes
    target.updated_by = current_user.db_id
    await session.commit()
    await session.refresh(target)
    asset_count = (
        await session.execute(
            select(func.count())
            .select_from(IpAsset)
            .where(IpAsset.watch_target_id == target.id, IpAsset.deleted_at.is_(None))
        )
    ).scalar_one()
    unread = (
        await session.execute(
            select(func.count())
            .select_from(IpWatchEvent)
            .where(
                IpWatchEvent.watch_target_id == target.id,
                IpWatchEvent.is_read.is_(False),
                IpWatchEvent.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    return _to_watch_target_out(target, asset_count, unread)


@ip_watch_targets_router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="ウォッチ対象の論理削除",
)
async def delete_watch_target(
    target_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> None:
    target = await _get_watch_target(session, target_id)
    from datetime import UTC, datetime

    target.deleted_at = datetime.now(UTC)
    target.updated_by = current_user.db_id
    await session.commit()


@ip_watch_targets_router.post(
    "/{target_id}/sync",
    response_model=IpWatchTargetSyncResult,
    summary="対象出願をポーリングして差分イベントを生成",
)
async def sync_watch_target(
    target_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpWatchTargetSyncResult:
    target = await _get_watch_target(session, target_id)
    try:
        calls, events, scanned = await ip_service.sync_watch_target(
            session,
            target=target,
        )
    except ip_service.JpoQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    await session.commit()
    return IpWatchTargetSyncResult(
        target_id=target.id,
        name=target.name,
        api_calls=calls,
        events_created=events,
        scanned_assets=scanned,
        message=f"{scanned} 件の出願を確認し、{events} 件のイベントを検知しました",
    )


ip_watch_events_router = APIRouter(prefix="/ip-watch-events", tags=["ip-watch"])


@ip_watch_events_router.get(
    "",
    response_model=Page[IpWatchEventOut],
    summary="ウォッチイベント一覧",
)
async def list_watch_events(
    watch_target_id: int | None = Query(default=None),
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[IpWatchEventOut]:
    stmt = select(IpWatchEvent).where(IpWatchEvent.deleted_at.is_(None))
    if watch_target_id is not None:
        stmt = stmt.where(IpWatchEvent.watch_target_id == watch_target_id)
    if unread_only:
        stmt = stmt.where(IpWatchEvent.is_read.is_(False))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    rows = list(
        (
            await session.execute(
                stmt.order_by(IpWatchEvent.detected_at.desc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    return Page[IpWatchEventOut](
        items=[IpWatchEventOut.model_validate(e) for e in rows],
        total=total,
        page=page,
        size=size,
    )


@ip_watch_events_router.patch(
    "/{event_id}/read",
    response_model=IpWatchEventOut,
    summary="イベントの既読化",
)
async def mark_event_read(
    event_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> IpWatchEventOut:
    event = await session.get(IpWatchEvent, event_id)
    if event is None or event.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    event.is_read = True
    await session.commit()
    await session.refresh(event)
    return IpWatchEventOut.model_validate(event)


# ---------------------------------------------------------------------------
# 審査書類 AI 解析
# ---------------------------------------------------------------------------

ip_documents_router = APIRouter(prefix="/ip-documents", tags=["ip-documents"])


@ip_documents_router.get(
    "/{document_id}",
    response_model=IpDocumentOut,
    summary="書類詳細（AI 解析結果含む）",
)
async def get_ip_document(
    document_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> IpDocumentOut:
    doc = await _get_document(session, document_id)
    return IpDocumentOut.model_validate(doc)


@ip_documents_router.post(
    "/{document_id}/analyze",
    response_model=IpDocumentAnalyzeResult,
    summary="書類テキストの AI 解析（要約・論点・対応方針・期限）",
)
async def analyze_ip_document(
    document_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(_WRITE_ROLE),
) -> IpDocumentAnalyzeResult:
    doc = await _get_document(session, document_id)
    try:
        doc = await ip_service.analyze_document(session, document=doc)
    except ip_service.IpServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    await session.commit()
    return IpDocumentAnalyzeResult(
        document_id=doc.id,
        doc_type=doc.doc_type,
        ai_model=doc.ai_model or "demo-local",
        summary=doc.ai_summary or "",
        findings=doc.ai_findings or {},
        analyzed_at=doc.analyzed_at,
    )


# ---------------------------------------------------------------------------
# dashboard / status
# ---------------------------------------------------------------------------

ip_dashboard_router = APIRouter(prefix="/ip-dashboard", tags=["ip"])


@ip_dashboard_router.get(
    "",
    response_model=IpDashboardOut,
    summary="知財管理ダッシュボードのサマリ",
)
async def get_ip_dashboard(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> IpDashboardOut:
    data = await ip_service.dashboard(session)
    return IpDashboardOut(
        total_assets=data["total_assets"],
        by_type=data["by_type"],
        by_status=data["by_status"],
        total_watch_targets=data["total_watch_targets"],
        active_watch_targets=data["active_watch_targets"],
        unread_events=data["unread_events"],
        recent_events=[IpWatchEventOut.model_validate(e) for e in data["recent_events"]],
        documents_total=data["documents_total"],
        documents_analyzed=data["documents_analyzed"],
        api_mode=data["api_mode"],
        api_configured=data["api_configured"],
    )


ip_status_router = APIRouter(prefix="/ip", tags=["ip"])


@ip_status_router.get(
    "/jpo-status",
    response_model=JpoStatusOut,
    summary="JPO API 接続状態",
)
async def get_jpo_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> JpoStatusOut:
    data = ip_service.jpo_status()
    return JpoStatusOut(**data)


# ルーターをまとめて export（app.api.v1.__init__ で include する）。
ip_router = APIRouter()
ip_router.include_router(ip_assets_router)
ip_router.include_router(ip_watch_targets_router)
ip_router.include_router(ip_watch_events_router)
ip_router.include_router(ip_documents_router)
ip_router.include_router(ip_dashboard_router)
ip_router.include_router(ip_status_router)

__all__ = ["ip_router"]
