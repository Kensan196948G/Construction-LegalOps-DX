"""証拠・eDiscovery 管理エンドポイント（Phase 3 §5.17 / Issue #124・#217-230）.

- POST   /evidence                          : 証拠登録（#217/#218/#219）
- GET    /evidence                          : 証拠一覧（#217）
- GET    /evidence/{id}                     : 証拠詳細取得（閲覧履歴に記録・#222）
- GET    /evidence/{id}/duplicates          : 重複ファイル検出（#225）
- GET    /evidence/{id}/timeline            : 証拠タイムライン（#223）
- GET    /evidence/{id}/view-history        : 証拠閲覧履歴（#222）
- GET    /evidence/{id}/export              : 証拠 Export（#224）
- POST   /evidence/{id}/custody             : Chain of Custody 追記（#220/#221）
- GET    /evidence/{id}/custody             : Chain of Custody 一覧
- POST   /evidence/{id}/legal-hold          : Legal Hold 紐付け
- POST   /evidence/email-ingest             : メール証拠取込（#226）
- POST   /evidence/hold-release-requests    : Legal Hold 解除申請（#230）
- GET    /evidence/hold-release-requests    : Legal Hold 解除申請一覧
- POST   /evidence/hold-release-requests/{id}/decide : 解除申請の決裁（#230）

証拠関連性の分類（#228）は登録時に決定論的なルールベースで自動実行され、
``EvidenceOut.relevance`` / ``relevance_score`` / ``relevance_note`` として
返却される。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceCustodyEventCreate,
    EvidenceCustodyEventOut,
    EvidenceEmailIngestRequest,
    EvidenceExportBundle,
    EvidenceHoldReleaseApprovalOut,
    EvidenceHoldReleaseDecision,
    EvidenceHoldReleaseRequestCreate,
    EvidenceLegalHoldLinkRequest,
    EvidenceOut,
    EvidenceTimelineItem,
    EvidenceViewHistoryItem,
)
from app.services import evidence_service

router = APIRouter(prefix="/evidence", tags=["evidence"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")
_APPROVE_ROLES = ("approver", "admin")
_PRIVILEGED_ROLES = ("admin", "auditor")


@router.get("", response_model=Page[EvidenceOut], summary="証拠一覧（#217）")
async def list_evidence(
    matter_id: int | None = Query(default=None),
    contract_id: int | None = Query(default=None),
    relevance: str | None = Query(default=None),
    is_duplicate: bool | None = Query(default=None),
    source_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[EvidenceOut]:
    items, total = await evidence_service.list_evidence(
        session,
        matter_id=matter_id,
        contract_id=contract_id,
        relevance=relevance,
        is_duplicate=is_duplicate,
        source_type=source_type,
        page=page,
        size=size,
    )
    # M10: PostgreSQL では RLS（migration 025）が既に行レベルで絞り込むが、
    # RLS の効かない環境（SQLite・テスト）向けの多層防御としてアプリ層でも
    # 案件 ACL・Legal Hold 倫理壁を確認する。ページ内の件数のみ絞り込み、
    # `total` は DB 側の件数のまま返す（正確な total 算出は RLS 側に委ねる）。
    if current_user.role not in _PRIVILEGED_ROLES:
        visible_items = []
        for item in items:
            try:
                await evidence_service.ensure_evidence_visible(
                    session, evidence=item, viewer=current_user
                )
            except ForbiddenError:
                continue
            visible_items.append(item)
        items = visible_items
    return Page[EvidenceOut](
        items=[EvidenceOut.model_validate(i) for i in items], total=total, page=page, size=size
    )


@router.post("", response_model=EvidenceOut, status_code=201, summary="証拠登録（#217/#218/#219）")
async def create_evidence(
    body: EvidenceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EvidenceOut:
    row = await evidence_service.create_evidence(
        session,
        actor_id=current_user.db_id,
        title=body.title,
        description=body.description,
        source_type=body.source_type,
        matter_id=body.matter_id,
        contract_id=body.contract_id,
        filename=body.filename,
        mime_type=body.mime_type,
        storage=body.storage,
        storage_ref=body.storage_ref,
        file_content_base64=body.file_content_base64,
        checksum_sha256=body.checksum_sha256,
        collected_by=current_user.db_id,
        collected_by_name=body.collected_by_name,
        collected_at=body.collected_at,
    )
    return EvidenceOut.model_validate(row)


@router.post(
    "/email-ingest",
    response_model=EvidenceOut,
    status_code=201,
    summary="メール証拠取込（#226）",
)
async def email_ingest(
    body: EvidenceEmailIngestRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EvidenceOut:
    row = await evidence_service.ingest_email_evidence(
        session,
        actor_id=current_user.db_id,
        raw_eml=body.raw_eml,
        matter_id=body.matter_id,
        contract_id=body.contract_id,
        collected_by=current_user.db_id,
        collected_by_name=body.collected_by_name,
    )
    return EvidenceOut.model_validate(row)


# ---------------------------------------------------------------------------
# Legal Hold 解除承認（固定パスは {evidence_id} より前に定義する）
# ---------------------------------------------------------------------------


@router.post(
    "/hold-release-requests",
    response_model=EvidenceHoldReleaseApprovalOut,
    status_code=201,
    summary="Legal Hold 解除申請（#230）",
)
async def request_hold_release(
    body: EvidenceHoldReleaseRequestCreate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EvidenceHoldReleaseApprovalOut:
    approval = await evidence_service.request_hold_release(
        session,
        legal_hold_id=body.legal_hold_id,
        requested_by=current_user.db_id,
        reason=body.reason,
        evidence_id=body.evidence_id,
    )
    return EvidenceHoldReleaseApprovalOut.model_validate(approval)


@router.get(
    "/hold-release-requests",
    response_model=list[EvidenceHoldReleaseApprovalOut],
    summary="Legal Hold 解除申請一覧（#230）",
)
async def list_hold_release_requests(
    legal_hold_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[EvidenceHoldReleaseApprovalOut]:
    rows = await evidence_service.list_hold_release_approvals(
        session, legal_hold_id=legal_hold_id, status=status_
    )
    return [EvidenceHoldReleaseApprovalOut.model_validate(r) for r in rows]


@router.post(
    "/hold-release-requests/{approval_id}/decide",
    response_model=EvidenceHoldReleaseApprovalOut,
    summary="Legal Hold 解除申請の決裁（#230・申請者本人による決裁は 403）",
)
async def decide_hold_release(
    approval_id: int,
    body: EvidenceHoldReleaseDecision,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_APPROVE_ROLES)),
) -> EvidenceHoldReleaseApprovalOut:
    approval = await evidence_service.decide_hold_release(
        session,
        approval_id=approval_id,
        decided_by=current_user.db_id,
        approve=body.approve,
        decision_note=body.decision_note,
    )
    return EvidenceHoldReleaseApprovalOut.model_validate(approval)


# ---------------------------------------------------------------------------
# 証拠単位の操作
# ---------------------------------------------------------------------------


@router.get(
    "/{evidence_id}", response_model=EvidenceOut, summary="証拠詳細（閲覧履歴に記録・#222）"
)
async def get_evidence(
    evidence_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> EvidenceOut:
    evidence = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=evidence, viewer=current_user)
    row = await evidence_service.record_view(
        session, evidence_id=evidence_id, viewer_id=current_user.db_id
    )
    return EvidenceOut.model_validate(row)


@router.get(
    "/{evidence_id}/duplicates",
    response_model=list[EvidenceOut],
    summary="重複ファイル検出（#225・同一 SHA-256 ハッシュ）",
)
async def get_duplicates(
    evidence_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[EvidenceOut]:
    base = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=base, viewer=current_user)
    rows = await evidence_service.list_duplicates(session, evidence_id=evidence_id)
    if current_user.role not in _PRIVILEGED_ROLES:
        visible_rows = []
        for r in rows:
            try:
                await evidence_service.ensure_evidence_visible(
                    session, evidence=r, viewer=current_user
                )
            except ForbiddenError:
                continue
            visible_rows.append(r)
        rows = visible_rows
    return [EvidenceOut.model_validate(r) for r in rows]


@router.get(
    "/{evidence_id}/timeline",
    response_model=list[EvidenceTimelineItem],
    summary="証拠タイムライン（#223・Chain of Custody + 監査ログ）",
)
async def get_timeline(
    evidence_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[EvidenceTimelineItem]:
    evidence = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=evidence, viewer=current_user)
    items = await evidence_service.get_timeline(session, evidence_id=evidence_id)
    return [EvidenceTimelineItem.model_validate(i) for i in items]


@router.get(
    "/{evidence_id}/view-history",
    response_model=list[EvidenceViewHistoryItem],
    summary="証拠閲覧履歴（#222）",
)
async def get_view_history(
    evidence_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[EvidenceViewHistoryItem]:
    evidence = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=evidence, viewer=current_user)
    rows, _total = await evidence_service.get_view_history(
        session, evidence_id=evidence_id, page=page, size=size
    )
    return [
        EvidenceViewHistoryItem(
            id=r.id, occurred_at=r.occurred_at, action=r.action, actor_id=r.actor_id
        )
        for r in rows
    ]


@router.get(
    "/{evidence_id}/export",
    response_model=EvidenceExportBundle,
    summary="証拠 Export（#224・メタデータ + タイムライン + 整合性検証結果）",
)
async def export_evidence(
    evidence_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> EvidenceExportBundle:
    evidence = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=evidence, viewer=current_user)
    bundle = await evidence_service.export_evidence_bundle(
        session, evidence_id=evidence_id, actor_id=current_user.db_id
    )
    return EvidenceExportBundle.model_validate(bundle)


@router.get(
    "/{evidence_id}/custody",
    response_model=list[EvidenceCustodyEventOut],
    summary="Chain of Custody 一覧（#220）",
)
async def list_custody(
    evidence_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[EvidenceCustodyEventOut]:
    evidence = await evidence_service.get_evidence(session, evidence_id=evidence_id)
    await evidence_service.ensure_evidence_visible(session, evidence=evidence, viewer=current_user)
    rows = await evidence_service.list_custody_events(session, evidence_id=evidence_id)
    return [EvidenceCustodyEventOut.model_validate(r) for r in rows]


@router.post(
    "/{evidence_id}/custody",
    response_model=EvidenceCustodyEventOut,
    status_code=201,
    summary="Chain of Custody 追記（#220/#221 収集者・受け渡し記録）",
)
async def add_custody_event(
    evidence_id: int,
    body: EvidenceCustodyEventCreate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EvidenceCustodyEventOut:
    row = await evidence_service.add_custody_event(
        session,
        evidence_id=evidence_id,
        actor_id=current_user.db_id,
        action=body.action,
        actor_name=body.actor_name,
        from_custodian=body.from_custodian,
        to_custodian=body.to_custodian,
        notes=body.notes,
    )
    return EvidenceCustodyEventOut.model_validate(row)


@router.post(
    "/{evidence_id}/legal-hold",
    response_model=EvidenceOut,
    summary="既存 Legal Hold の証拠への紐付け",
)
async def link_legal_hold(
    evidence_id: int,
    body: EvidenceLegalHoldLinkRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EvidenceOut:
    row = await evidence_service.link_legal_hold(
        session,
        evidence_id=evidence_id,
        legal_hold_id=body.legal_hold_id,
        actor_id=current_user.db_id,
    )
    return EvidenceOut.model_validate(row)
