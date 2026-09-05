"""JV（共同企業体）管理の業務サービス（ロードマップ #61〜#70）.

- #61 JV 台帳: JV の登録・状態遷移（prospecting→active→completed/dissolved）。
- #63 代表会社・構成員管理: 代表は 1 名の制約を検証。
- #64 出資比率 / #65 損益分担率: 構成員の比率合計 100% を決定論的に検証。
- #62 JV 協定書管理: draft → signed（→ terminated）。
- #69 JV 内紛争・請求: open → responded / cancelled。
- #70 終了・清算: pending → settled（JV が completed/dissolved のみ清算可）。

状態遷移は ``app.services.jv_service`` のルールエンジンが唯一の正（AI 不使用）。
#67 JV 承認ルートは既存 workflow_engine を、#68 差分 AI レビューは reviews 基盤を
流用する（本サービスでは扱わない）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.enums import (
    JvAgreementStatus,
    JvDisputeStatus,
    JvMemberRole,
    JvSettlementStatus,
    JvStatus,
)
from app.models.joint_venture import (
    JointVenture,
    JvAgreement,
    JvDispute,
    JvMember,
    JvSettlement,
)

logger = structlog.get_logger(__name__)

_EQUITY_TOLERANCE = 0.01  # 出資比率合計 100% の許容誤差（浮動小数点）


async def _build_jv_no(session: AsyncSession) -> str:
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"JV-{year}-"
    last = (
        await session.execute(
            select(JointVenture.jv_no)
            .where(JointVenture.jv_no.like(f"{prefix}%"))
            .order_by(JointVenture.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


async def get_jv(session: AsyncSession, *, jv_id: int) -> JointVenture:
    row = await session.get(JointVenture, jv_id)
    if row is None:
        raise NotFoundError(f"JV が見つかりません（id={jv_id}）")
    return row


async def list_jvs(
    session: AsyncSession,
    *,
    status: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[JointVenture], int]:
    stmt = select(JointVenture)
    if status is not None:
        try:
            stmt = stmt.where(JointVenture.status == JvStatus(status).value)
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(JointVenture.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def create_jv(
    session: AsyncSession,
    *,
    actor_id: int | None,
    name: str,
    representative_name: str | None = None,
    works_title: str | None = None,
    contract_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    notes: str | None = None,
) -> JointVenture:
    """#61 JV を登録する（prospecting）."""
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    if start_date and end_date and end_date < start_date:
        raise ValidationError("end_date は start_date 以上としてください。")
    row = JointVenture(
        jv_no="",  # flush 後に採番（JV-YYYY-NNNNNN）
        name=name,
        status=JvStatus.PROSPECTING.value,
        representative_name=representative_name,
        works_title=works_title,
        contract_id=contract_id,
        start_date=start_date,
        end_date=end_date,
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.jv_no = await _build_jv_no(session)
    await session.flush()
    await session.refresh(row)
    return row


async def set_jv_status(
    session: AsyncSession,
    *,
    jv_id: int,
    actor_id: int | None,
    status: str,
) -> JointVenture:
    """#61 JV の状態遷移（prospecting→active→completed/dissolved・戻しは不可）."""
    row = await get_jv(session, jv_id=jv_id)
    try:
        next_status = JvStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な状態: {status!r}") from exc
    if row.status == next_status:
        raise ConflictError("同一状態への遷移です。")
    allowed = {
        JvStatus.PROSPECTING.value: {JvStatus.ACTIVE.value, JvStatus.DISSOLVED.value},
        JvStatus.ACTIVE.value: {JvStatus.COMPLETED.value, JvStatus.DISSOLVED.value},
        JvStatus.COMPLETED.value: set(),
        JvStatus.DISSOLVED.value: set(),
    }
    if next_status not in allowed.get(row.status, set()):
        raise ConflictError(
            f"状態遷移が不正です（{row.status} → {next_status}）。"
            "戻し・完了後の変更はできません。"
        )
    row.status = next_status
    if next_status in (JvStatus.COMPLETED.value, JvStatus.DISSOLVED.value):
        row.dissolved_at = datetime.now(UTC)
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# --------------------------------------------------- #63/#64/#65 構成員 ---
async def list_members(
    session: AsyncSession, *, jv_id: int
) -> list[JvMember]:
    jv = await get_jv(session, jv_id=jv_id)
    rows = (
        await session.execute(
            select(JvMember).where(JvMember.jv_id == jv.id).order_by(JvMember.id)
        )
    ).scalars().all()
    return list(rows)


async def add_member(
    session: AsyncSession,
    *,
    jv_id: int,
    actor_id: int | None,
    company_name: str,
    role: str = JvMemberRole.MEMBER.value,
    equity_ratio: float | None = None,
    profit_share_ratio: float | None = None,
    contact_email: str | None = None,
    notes: str | None = None,
) -> JvMember:
    """#63/#64/#65 構成員を追加する（代表は 1 名・比率合計 100% 検証）."""
    jv = await get_jv(session, jv_id=jv_id)
    if jv.status in (JvStatus.COMPLETED.value, JvStatus.DISSOLVED.value):
        raise ConflictError("完了・解散済みの JV には構成員を追加できません。")
    try:
        role_value = JvMemberRole(role).value
    except ValueError as exc:
        raise ValidationError(f"不正な役割: {role!r}") from exc
    for ratio_value, label in (
        (equity_ratio, "出資比率"),
        (profit_share_ratio, "損益分担率"),
    ):
        if ratio_value is not None and not 0.0 <= ratio_value <= 100.0:
            raise ValidationError(f"{label}は 0〜100（%）で指定してください。")

    if role_value == JvMemberRole.REPRESENTATIVE.value:
        existing_rep = (
            await session.execute(
                select(JvMember).where(
                    JvMember.jv_id == jv_id,
                    JvMember.role == JvMemberRole.REPRESENTATIVE.value,
                    JvMember.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing_rep is not None:
            raise ConflictError("代表会社は 1 社のみです（既存の代表を先に無効化してください）。")
        jv.representative_name = company_name

    # #64 出資比率の合計 100% を「追加前に」検証する（flush 後に例外にしない）
    await _validate_member_ratios(session, jv_id=jv_id, additional_equity=equity_ratio)

    row = JvMember(
        jv_id=jv_id,
        role=role_value,
        company_name=company_name,
        equity_ratio=equity_ratio,
        profit_share_ratio=profit_share_ratio,
        contact_email=contact_email,
        notes=notes,
        is_active=True,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _validate_member_ratios(
    session: AsyncSession, *, jv_id: int, additional_equity: float | None = None
) -> None:
    """#64 出資比率の合計が 100% を超えていたら拒否する（追加前検証・決定論的）."""
    rows = (
        await session.execute(
            select(JvMember).where(
                JvMember.jv_id == jv_id, JvMember.is_active.is_(True)
            )
        )
    ).scalars().all()
    equity_total = sum(
        (m.equity_ratio or 0.0) for m in rows
    ) + (additional_equity or 0.0)
    if equity_total > 100.0 + _EQUITY_TOLERANCE:
        raise ValidationError(
            f"出資比率の合計が 100% を超えています（合計 {equity_total:.1f}%）。"
        )


async def list_agreements(
    session: AsyncSession, *, jv_id: int
) -> list[JvAgreement]:
    await get_jv(session, jv_id=jv_id)
    rows = (
        await session.execute(
            select(JvAgreement).where(JvAgreement.jv_id == jv_id).order_by(JvAgreement.id)
        )
    ).scalars().all()
    return list(rows)


async def create_agreement(
    session: AsyncSession,
    *,
    jv_id: int,
    actor_id: int | None,
    title: str,
    summary: str | None = None,
    signed_at: date | None = None,
    document_url: str | None = None,
) -> JvAgreement:
    """#62 JV 協定書を登録する（draft・signed_at あれば signed）."""
    await get_jv(session, jv_id=jv_id)
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"JVA-{year}-"
    last = (
        await session.execute(
            select(JvAgreement.agreement_no)
            .where(JvAgreement.agreement_no.like(f"{prefix}%"))
            .order_by(JvAgreement.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    status_value = (
        JvAgreementStatus.SIGNED.value if signed_at else JvAgreementStatus.DRAFT.value
    )
    row = JvAgreement(
        jv_id=jv_id,
        agreement_no=f"{prefix}{next_seq:06d}",
        status=status_value,
        title=title,
        summary=summary,
        signed_at=signed_at,
        document_url=document_url,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def terminate_agreement(
    session: AsyncSession,
    *,
    agreement_id: int,
    actor_id: int | None,
) -> JvAgreement:
    """#62 協定書を終了する（signed → terminated）。"""
    row = await session.get(JvAgreement, agreement_id)
    if row is None:
        raise NotFoundError(f"JV 協定書が見つかりません（id={agreement_id}）")
    if row.status != JvAgreementStatus.SIGNED.value:
        raise ConflictError("終了できるのは signed（締結済み）の協定書のみです。")
    row.status = JvAgreementStatus.TERMINATED.value
    row.terminated_at = date.today()
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# --------------------------------------------------------------- #69 紛争 ---
async def list_disputes(session: AsyncSession, *, jv_id: int) -> list[JvDispute]:
    await get_jv(session, jv_id=jv_id)
    rows = (
        await session.execute(
            select(JvDispute).where(JvDispute.jv_id == jv_id).order_by(JvDispute.id)
        )
    ).scalars().all()
    return list(rows)


async def create_dispute(
    session: AsyncSession,
    *,
    jv_id: int,
    actor_id: int | None,
    title: str,
    claimant_name: str | None = None,
    respondent_name: str | None = None,
    amount_claimed_jpy: int | None = None,
    detail: str | None = None,
) -> JvDispute:
    """#69 JV 内紛争・請求を記録する（open）."""
    await get_jv(session, jv_id=jv_id)
    if amount_claimed_jpy is not None and amount_claimed_jpy < 0:
        raise ValidationError("請求額は 0 以上です。")
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"JVD-{year}-"
    last = (
        await session.execute(
            select(JvDispute.dispute_no)
            .where(JvDispute.dispute_no.like(f"{prefix}%"))
            .order_by(JvDispute.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    row = JvDispute(
        jv_id=jv_id,
        dispute_no=f"{prefix}{next_seq:06d}",
        status=JvDisputeStatus.OPEN.value,
        title=title,
        claimant_name=claimant_name,
        respondent_name=respondent_name,
        amount_claimed_jpy=amount_claimed_jpy,
        detail=detail,
        raised_at=date.today(),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def respond_dispute(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    response_note: str,
) -> JvDispute:
    """#69 紛争への回答を記録する（open → responded）。"""
    row = await session.get(JvDispute, dispute_id)
    if row is None:
        raise NotFoundError(f"JV 内紛争が見つかりません（id={dispute_id}）")
    if row.status != JvDisputeStatus.OPEN.value:
        raise ConflictError("回答できるのは open（協議中）のみです。")
    row.status = JvDisputeStatus.RESPONDED.value
    row.response_note = response_note
    row.responded_at = datetime.now(UTC)
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# --------------------------------------------------------------- #70 清算 ---
async def list_settlements(session: AsyncSession, *, jv_id: int) -> list[JvSettlement]:
    await get_jv(session, jv_id=jv_id)
    rows = (
        await session.execute(
            select(JvSettlement).where(JvSettlement.jv_id == jv_id).order_by(JvSettlement.id)
        )
    ).scalars().all()
    return list(rows)


async def create_settlement(
    session: AsyncSession,
    *,
    jv_id: int,
    actor_id: int | None,
    title: str,
    settlement_amount_jpy: int | None = None,
    detail: str | None = None,
) -> JvSettlement:
    """#70 清算を記録する（pending・JV が完了/解散済みであること）."""
    jv = await get_jv(session, jv_id=jv_id)
    if jv.status not in (JvStatus.COMPLETED.value, JvStatus.DISSOLVED.value):
        raise ConflictError(
            "清算は JV が completed / dissolved の場合のみ記録できます。"
        )
    if settlement_amount_jpy is not None and settlement_amount_jpy < 0:
        raise ValidationError("清算金額は 0 以上です。")
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"JVS-{year}-"
    last = (
        await session.execute(
            select(JvSettlement.settlement_no)
            .where(JvSettlement.settlement_no.like(f"{prefix}%"))
            .order_by(JvSettlement.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    row = JvSettlement(
        jv_id=jv_id,
        settlement_no=f"{prefix}{next_seq:06d}",
        status=JvSettlementStatus.PENDING.value,
        title=title,
        settlement_amount_jpy=settlement_amount_jpy,
        detail=detail,
        recorded_by=actor_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def settle(
    session: AsyncSession,
    *,
    settlement_id: int,
    actor_id: int | None,
) -> JvSettlement:
    """#70 清算を完了する（pending → settled）。"""
    row = await session.get(JvSettlement, settlement_id)
    if row is None:
        raise NotFoundError(f"JV 清算が見つかりません（id={settlement_id}）")
    if row.status != JvSettlementStatus.PENDING.value:
        raise ConflictError("清算済みのレコードは再度清算できません。")
    row.status = JvSettlementStatus.SETTLED.value
    row.settled_at = date.today()
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def dashboard_summary(session: AsyncSession) -> dict[str, object]:
    """JV サマリー（台帳/協定/紛争/清算の open 件数・状態別集計）."""
    status_rows = (
        await session.execute(
            select(JointVenture.status, func.count()).group_by(JointVenture.status)
        )
    ).all()
    agreements_signed = (
        await session.execute(
            select(func.count())
            .select_from(JvAgreement)
            .where(JvAgreement.status == JvAgreementStatus.SIGNED.value)
        )
    ).scalar_one()
    disputes_open = (
        await session.execute(
            select(func.count())
            .select_from(JvDispute)
            .where(JvDispute.status == JvDisputeStatus.OPEN.value)
        )
    ).scalar_one()
    settlements_pending = (
        await session.execute(
            select(func.count())
            .select_from(JvSettlement)
            .where(JvSettlement.status == JvSettlementStatus.PENDING.value)
        )
    ).scalar_one()
    return {
        "jvs_by_status": {t: int(c) for t, c in status_rows},
        "agreements_signed": int(agreements_signed),
        "disputes_open": int(disputes_open),
        "settlements_pending": int(settlements_pending),
    }


__all__ = [
    "add_member",
    "create_agreement",
    "create_dispute",
    "create_jv",
    "create_settlement",
    "dashboard_summary",
    "get_jv",
    "list_agreements",
    "list_disputes",
    "list_jvs",
    "list_members",
    "list_settlements",
    "respond_dispute",
    "set_jv_status",
    "settle",
    "terminate_agreement",
]
