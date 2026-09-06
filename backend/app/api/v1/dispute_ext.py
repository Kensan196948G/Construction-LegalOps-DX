"""紛争・クレーム管理高度化エンドポイント（ロードマップ #97〜#112 / Issue #121）.

既存 ``disputes_router``（``app.api.v1.business``）を拡張する形の別ルーターと
して実装する（prefix は同じ ``/disputes`` だが、サブパスは重複しない）。

- ``POST /disputes/{id}/claim-notice``                … #97 通知書生成
- ``POST /disputes/{id}/notice-deadline/auto-judge``  … #98 通知期限自動判定
- ``GET  /disputes/alerts/time-bar``                  … #99/#112 Time Bar 一覧
- ``GET  /disputes/{id}/time-bar``                    … #99/#112 単一案件タイマー
- ``POST /disputes/{id}/delay-events`` / ``GET``      … #100 遅延事象台帳
- ``GET  /disputes/{id}/delay-events/summary``        … #101/#102/#103 集計
- ``PATCH /disputes/delay-events/{id}/eot``           … #104 EOT 判定
- ``GET  /disputes/{id}/evidence-score``              … #105/#106 証拠充足度
- ``GET  /disputes/{id}/chronology``                  … #107/#108 Chronology
- ``POST /disputes/{id}/arguments`` / ``GET``         … #109 主張・反論マトリクス
- ``POST /disputes/{id}/settlement-options`` / ``GET`` / ``PATCH`` /
  ``GET .../compare``                                  … #110 和解案比較
- ``POST /disputes/{id}/stages`` / ``GET``            … #111 訴訟・ADR ステージ
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.dispute_ext import (
    DisputeArgumentPositionCreate,
    DisputeArgumentPositionOut,
    DisputeChronologyEntryOut,
    DisputeClaimNoticeOut,
    DisputeClaimNoticeRequest,
    DisputeDelayEventCreate,
    DisputeDelayEventEotUpdate,
    DisputeDelayEventOut,
    DisputeDelaySummaryOut,
    DisputeEvidenceScoreOut,
    DisputeNoticeDeadlineAutoJudgeOut,
    DisputeNoticeDeadlineAutoJudgeRequest,
    DisputeProceedingStageCreate,
    DisputeProceedingStageOut,
    DisputeSettlementOptionCreate,
    DisputeSettlementOptionOut,
    DisputeSettlementOptionUpdate,
    DisputeTimeBarAlertOut,
)
from app.services import audit_service, dispute_ext_service

router = APIRouter(prefix="/disputes", tags=["dispute-ext"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_type: str,
    target_id: int,
    payload: dict[str, object] | None = None,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request=request,
        payload=payload,
    )


# --------------------------------------------------------- #97 通知書生成 ---
@router.post(
    "/{dispute_id}/claim-notice",
    response_model=DisputeClaimNoticeOut,
    summary="クレーム通知書生成（#97・決定論的テンプレート処理・AI 不使用）",
)
async def generate_claim_notice(
    dispute_id: int,
    body: DisputeClaimNoticeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> DisputeClaimNoticeOut:
    dispute = await dispute_ext_service.get_dispute_full(session, dispute_id=dispute_id)
    result = dispute_ext_service.generate_claim_notice(
        dispute,
        sender_name=body.sender_name,
        recipient_name=body.recipient_name,
        notice_date=body.notice_date,
        extra_note=body.extra_note,
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.claim_notice.generate",
        target_type="disputes",
        target_id=dispute_id,
    )
    return DisputeClaimNoticeOut(**result)


# --------------------------------------------------- #98 通知期限自動判定 ---
@router.post(
    "/{dispute_id}/notice-deadline/auto-judge",
    response_model=DisputeNoticeDeadlineAutoJudgeOut,
    summary="通知期限自動判定（#98・決定論的既定日数テーブル）",
)
async def auto_judge_notice_deadline(
    dispute_id: int,
    body: DisputeNoticeDeadlineAutoJudgeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeNoticeDeadlineAutoJudgeOut:
    result = await dispute_ext_service.apply_notice_deadline_auto_judge(
        session,
        dispute_id=dispute_id,
        actor_id=current_user.db_id,
        event_date=body.event_date,
        override_days=body.override_days,
        apply=body.apply,
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.notice_deadline.auto_judge",
        target_type="disputes",
        target_id=dispute_id,
        payload={"applied": result["applied"], "notice_period_days": result["notice_period_days"]},
    )
    return DisputeNoticeDeadlineAutoJudgeOut(**result)


# --------------------------------------------- #99/#112 Time Bar / 時効 ---
@router.get(
    "/alerts/time-bar",
    response_model=list[DisputeTimeBarAlertOut],
    summary="Time Bar 警告一覧（#99・消滅時効タイマー #112・未解決案件横断）",
)
async def list_time_bar_alerts(
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeTimeBarAlertOut]:
    alerts = await dispute_ext_service.list_time_bar_alerts(session)
    return [DisputeTimeBarAlertOut(**a) for a in alerts]


@router.get(
    "/{dispute_id}/time-bar",
    response_model=DisputeTimeBarAlertOut,
    summary="単一案件の Time Bar / 消滅時効タイマー（#99/#112）",
)
async def get_time_bar_status(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> DisputeTimeBarAlertOut:
    dispute = await dispute_ext_service.get_dispute_full(session, dispute_id=dispute_id)
    result = dispute_ext_service.dispute_time_bar_status(dispute)
    return DisputeTimeBarAlertOut(**{**result, "severity": result["severity"] or "ok"})


# --------------------------------------------------- #100〜#104 遅延事象 ---
@router.post(
    "/{dispute_id}/delay-events",
    response_model=DisputeDelayEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="遅延事象を登録（#100 台帳・#101 原因分類・#102 追加費用・#103 損害額）",
)
async def add_delay_event(
    dispute_id: int,
    body: DisputeDelayEventCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeDelayEventOut:
    row = await dispute_ext_service.add_delay_event(
        session, dispute_id=dispute_id, actor_id=current_user.db_id, data=body.model_dump()
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.delay_event.create",
        target_type="dispute_delay_events",
        target_id=row.id,
        payload={"dispute_id": dispute_id, "cause_category": row.cause_category},
    )
    return DisputeDelayEventOut.model_validate(row)


@router.get(
    "/{dispute_id}/delay-events",
    response_model=list[DisputeDelayEventOut],
    summary="遅延事象一覧（#100）",
)
async def list_delay_events(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeDelayEventOut]:
    rows = await dispute_ext_service.list_delay_events(session, dispute_id=dispute_id)
    return [DisputeDelayEventOut.model_validate(r) for r in rows]


@router.get(
    "/{dispute_id}/delay-events/summary",
    response_model=DisputeDelaySummaryOut,
    summary="遅延事象の原因別集計（#101 原因分類・#102 追加費用・#103 損害額）",
)
async def delay_events_summary(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> DisputeDelaySummaryOut:
    result = await dispute_ext_service.delay_summary(session, dispute_id=dispute_id)
    return DisputeDelaySummaryOut(**result)


@router.patch(
    "/delay-events/{delay_event_id}/eot",
    response_model=DisputeDelayEventOut,
    summary="EOT／工期延長の判定（#104・pending からのみ更新）",
)
async def update_delay_event_eot(
    delay_event_id: int,
    body: DisputeDelayEventEotUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeDelayEventOut:
    row = await dispute_ext_service.update_delay_event_eot(
        session,
        delay_event_id=delay_event_id,
        actor_id=current_user.db_id,
        eot_status=body.eot_status,
        eot_days_granted=body.eot_days_granted,
        eot_note=body.eot_note,
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.delay_event.eot_decide",
        target_type="dispute_delay_events",
        target_id=row.id,
        payload={"eot_status": row.eot_status, "eot_days_granted": row.eot_days_granted},
    )
    return DisputeDelayEventOut.model_validate(row)


# --------------------------------------------- #105/#106 証拠充足度スコア ---
@router.get(
    "/{dispute_id}/evidence-score",
    response_model=DisputeEvidenceScoreOut,
    summary="証拠充足度スコア・証拠不足検知（#105/#106・ルールベース・AI 不使用）",
)
async def evidence_score(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> DisputeEvidenceScoreOut:
    dispute = await dispute_ext_service.get_dispute_full(session, dispute_id=dispute_id)
    result = dispute_ext_service.evidence_sufficiency_score(dispute)
    return DisputeEvidenceScoreOut(**result)


# --------------------------------------------- #107/#108 Claim Chronology ---
@router.get(
    "/{dispute_id}/chronology",
    response_model=list[DisputeChronologyEntryOut],
    summary="Claim Chronology 自動生成（#107 写真・議事録・メール統合／#108 時系列生成）",
)
async def chronology(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeChronologyEntryOut]:
    dispute = await dispute_ext_service.get_dispute_full(session, dispute_id=dispute_id)
    entries = dispute_ext_service.build_chronology(dispute)
    return [DisputeChronologyEntryOut(**e) for e in entries]


# --------------------------------------------------- #109 主張・反論マトリクス ---
@router.post(
    "/{dispute_id}/arguments",
    response_model=DisputeArgumentPositionOut,
    status_code=status.HTTP_201_CREATED,
    summary="主張・反論マトリクスへ登録（#109）",
)
async def add_argument_position(
    dispute_id: int,
    body: DisputeArgumentPositionCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeArgumentPositionOut:
    row = await dispute_ext_service.add_argument_position(
        session, dispute_id=dispute_id, actor_id=current_user.db_id, data=body.model_dump()
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.argument.create",
        target_type="dispute_argument_positions",
        target_id=row.id,
        payload={"dispute_id": dispute_id, "issue_no": row.issue_no, "party": row.party},
    )
    return DisputeArgumentPositionOut.model_validate(row)


@router.get(
    "/{dispute_id}/arguments",
    response_model=list[DisputeArgumentPositionOut],
    summary="主張・反論マトリクス一覧（#109）",
)
async def list_argument_positions(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeArgumentPositionOut]:
    rows = await dispute_ext_service.list_argument_positions(session, dispute_id=dispute_id)
    return [DisputeArgumentPositionOut.model_validate(r) for r in rows]


# --------------------------------------------------------- #110 和解案比較 ---
@router.post(
    "/{dispute_id}/settlement-options",
    response_model=DisputeSettlementOptionOut,
    status_code=status.HTTP_201_CREATED,
    summary="和解案を登録（#110）",
)
async def add_settlement_option(
    dispute_id: int,
    body: DisputeSettlementOptionCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeSettlementOptionOut:
    row = await dispute_ext_service.add_settlement_option(
        session, dispute_id=dispute_id, actor_id=current_user.db_id, data=body.model_dump()
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.settlement_option.create",
        target_type="dispute_settlement_options",
        target_id=row.id,
        payload={"dispute_id": dispute_id},
    )
    return DisputeSettlementOptionOut.model_validate(row)


@router.get(
    "/{dispute_id}/settlement-options",
    response_model=list[DisputeSettlementOptionOut],
    summary="和解案一覧（#110）",
)
async def list_settlement_options(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeSettlementOptionOut]:
    rows = await dispute_ext_service.list_settlement_options(session, dispute_id=dispute_id)
    return [DisputeSettlementOptionOut.model_validate(r) for r in rows]


@router.get(
    "/{dispute_id}/settlement-options/compare",
    summary="和解案比較（#110・期待値順・最有力案を推奨表示）",
)
async def compare_settlement_options(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[dict[str, object]]:
    return await dispute_ext_service.compare_settlement_options(session, dispute_id=dispute_id)


@router.patch(
    "/settlement-options/{option_id}",
    response_model=DisputeSettlementOptionOut,
    summary="和解案の更新（#110・状態遷移・内容修正）",
)
async def update_settlement_option(
    option_id: int,
    body: DisputeSettlementOptionUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeSettlementOptionOut:
    row = await dispute_ext_service.update_settlement_option(
        session,
        option_id=option_id,
        actor_id=current_user.db_id,
        data=body.model_dump(exclude_unset=True),
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.settlement_option.update",
        target_type="dispute_settlement_options",
        target_id=row.id,
        payload={"status": row.status},
    )
    return DisputeSettlementOptionOut.model_validate(row)


# --------------------------------------------- #111 訴訟・ADR ステージ管理 ---
@router.post(
    "/{dispute_id}/stages",
    response_model=DisputeProceedingStageOut,
    status_code=status.HTTP_201_CREATED,
    summary="訴訟・ADR ステージの追加／遷移（#111）",
)
async def add_proceeding_stage(
    dispute_id: int,
    body: DisputeProceedingStageCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> DisputeProceedingStageOut:
    row = await dispute_ext_service.add_proceeding_stage(
        session, dispute_id=dispute_id, actor_id=current_user.db_id, data=body.model_dump()
    )
    await _audit(
        session,
        request,
        current_user,
        action="dispute.stage.add",
        target_type="dispute_proceeding_stages",
        target_id=row.id,
        payload={"dispute_id": dispute_id, "stage": row.stage},
    )
    return DisputeProceedingStageOut.model_validate(row)


@router.get(
    "/{dispute_id}/stages",
    response_model=list[DisputeProceedingStageOut],
    summary="訴訟・ADR ステージ履歴（#111）",
)
async def list_proceeding_stages(
    dispute_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[DisputeProceedingStageOut]:
    rows = await dispute_ext_service.list_proceeding_stages(session, dispute_id=dispute_id)
    return [DisputeProceedingStageOut.model_validate(r) for r in rows]
