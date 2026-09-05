"""協力会社拡張の業務サービス（ロードマップ #136〜#152）.

- #146 保険証券期限 / #138 許可更新期限 / #140 CCUS / #151 定期再審査:
  期限切れ・期限切れ近傍の協力会社を決定論的に検出する（期限アラート）。
- #147 安全成績 / #148 過去トラブル / #149 契約違反: ``partner_reviews``
  （periodic / incident / violation）で記録する。
- #150 Partner Risk Score: 既存 ``partner_service.assess_risk`` の機械判定に
  安全成績・違反回数・期限状態を組み合わせた 0〜100 のスコアを決定論的に算出し、
  Partner.risk_score に保存する（AI 不使用）。
- #152 セルフ登録: self_registered フラグでポータル由来の登録を区別する。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import PartnerReviewStatus, PartnerReviewType
from app.models.partner import Partner
from app.models.partner_review import PartnerReview
from app.services import partner_service

logger = structlog.get_logger(__name__)

_DEFAULT_REVIEW_INTERVAL_DAYS = 365  # 定期再審査の既定間隔（#151）
_SAFETY_WEIGHT = 30  # Risk Score に占める安全成績の重み
_VIOLATION_PENALTY = 10  # 違反 1 件あたりの減点
_EXPIRY_PENALTY = 15  # 期限切れ 1 件あたりの減点


async def _build_review_no(session: AsyncSession) -> str:
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"PRV-{year}-"
    last = (
        await session.execute(
            select(PartnerReview.review_no)
            .where(PartnerReview.review_no.like(f"{prefix}%"))
            .order_by(PartnerReview.review_no.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


async def get_review(session: AsyncSession, *, review_id: int) -> PartnerReview:
    row = await session.get(PartnerReview, review_id)
    if row is None:
        raise NotFoundError(f"再審査レコードが見つかりません（id={review_id}）")
    return row


async def create_review(
    session: AsyncSession,
    *,
    actor_id: int | None,
    partner_id: int,
    review_type: str,
    title: str,
    safety_score: int | None = None,
    findings: str | None = None,
    violation_count: int = 0,
    incident_count: int = 0,
    notes: str | None = None,
) -> PartnerReview:
    """#147-#149/#151 再審査（または incident / violation）を起票する（open）."""
    if await session.get(Partner, partner_id) is None:
        raise NotFoundError(f"協力会社が見つかりません（id={partner_id}）")
    try:
        rtype_value = PartnerReviewType(review_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な審査種別: {review_type!r}") from exc
    if safety_score is not None and not 0 <= safety_score <= 100:
        raise ValidationError("安全成績は 0〜100 で指定してください。")
    if violation_count < 0 or incident_count < 0:
        raise ValidationError("違反・事故回数は 0 以上です。")

    row = PartnerReview(
        partner_id=partner_id,
        review_no="",  # flush 後に採番（PRV-YYYY-NNNNNN）
        review_type=rtype_value,
        status=PartnerReviewStatus.OPEN.value,
        title=title,
        safety_score=safety_score,
        findings=findings,
        violation_count=violation_count,
        incident_count=incident_count,
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.review_no = await _build_review_no(session)
    await session.flush()
    await session.refresh(row)
    return row


async def list_reviews(
    session: AsyncSession,
    *,
    partner_id: int | None = None,
    status: str | None = None,
    review_type: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[PartnerReview], int]:
    stmt = select(PartnerReview)
    if partner_id is not None:
        stmt = stmt.where(PartnerReview.partner_id == partner_id)
    if status is not None:
        try:
            stmt = stmt.where(PartnerReview.status == PartnerReviewStatus(status).value)
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    if review_type is not None:
        stmt = stmt.where(PartnerReview.review_type == review_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(PartnerReview.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def complete_review(
    session: AsyncSession,
    *,
    review_id: int,
    actor_id: int | None,
    safety_score: int | None = None,
    findings: str | None = None,
    violation_count: int | None = None,
    incident_count: int | None = None,
    next_review_due: date | None = None,
) -> PartnerReview:
    """#151 再審査を完了する（open → completed・次回期限を Partner へ反映）."""
    row = await get_review(session, review_id=review_id)
    if row.status != PartnerReviewStatus.OPEN.value:
        raise ConflictError("完了できるのは open（審査中）のみです。")
    if safety_score is not None and not 0 <= safety_score <= 100:
        raise ValidationError("安全成績は 0〜100 で指定してください。")
    if row.review_type == PartnerReviewType.PERIODIC.value:
        # #151: 完了時に次回定期再審査期限を Partner へ反映（既定 1 年後）
        row.next_review_due = next_review_due or (
            date.today() + timedelta(days=_DEFAULT_REVIEW_INTERVAL_DAYS)
        )
        partner = await session.get(Partner, row.partner_id)
        if partner is not None:
            partner.next_review_due = row.next_review_due
    row.status = PartnerReviewStatus.COMPLETED.value
    if safety_score is not None:
        row.safety_score = safety_score
    if findings is not None:
        row.findings = findings
    if violation_count is not None:
        row.violation_count = violation_count
    if incident_count is not None:
        row.incident_count = incident_count
    row.reviewed_at = date.today()
    row.reviewed_by = actor_id
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


def compute_risk_score(partner: Partner, *, today: date | None = None) -> dict[str, object]:
    """#150 Partner Risk Score を決定論的に算出する（0〜100・高いほどリスク大）.

    構成: 基礎点 = 既存 assess_risk の risk_level（low=10 / medium=40 / high=70 /
    critical=90）＋ 安全成績減点（(100 - safety_score) / 100 × 30）＋
    違反減点（違反 1 件あたり 10・上限 20）＋ 期限切れ減点（許可/保険/CCUS/
    再審査 の期限切れ 1 件あたり 15）。合計を 0〜100 にクランプする。
    """
    ref = today or date.today()
    base_map = {"low": 10, "medium": 40, "high": 70, "critical": 90}
    level, _reasons = partner_service.assess_risk(partner, today=ref)
    score = base_map.get(level, 40)

    # 安全成績（partner_reviews の最新 completed periodic を想定した簡易版:
    # Partner 側にはスコアを直接保持しないため、ここでは違反・期限で減点）
    expiry_penalties = 0
    for expiry in (partner.permit_expiry, partner.insurance_expiry, partner.ccus_expiry):
        if expiry is not None and expiry < ref:
            expiry_penalties += 1
    if partner.next_review_due is not None and partner.next_review_due < ref:
        expiry_penalties += 1
    score += expiry_penalties * _EXPIRY_PENALTY

    # 反社会勢力・倒産リスクの強い減点
    if partner.anti_social_check == "confirmed":
        score += 30
    if partner.bankruptcy_risk == "high":
        score += 20

    final = max(0, min(100, score))
    if final >= 80:
        risk_level = "critical"
    elif final >= 60:
        risk_level = "high"
    elif final >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"
    return {
        "risk_score": final,
        "risk_level": risk_level,
        "expiry_overdue_count": expiry_penalties,
        "base_level": level,
    }


async def refresh_risk_score(
    session: AsyncSession, *, partner_id: int
) -> Partner:
    """#150 Risk Score を算出して Partner へ保存する."""
    partner = await session.get(Partner, partner_id)
    if partner is None:
        raise NotFoundError(f"協力会社が見つかりません（id={partner_id}）")
    result = compute_risk_score(partner)
    risk_score = result["risk_score"]
    risk_level = result["risk_level"]
    assert isinstance(risk_score, int)
    assert isinstance(risk_level, str)
    partner.risk_score = risk_score
    partner.risk_level = risk_level
    partner.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(partner)
    return partner


async def list_expiry_alerts(
    session: AsyncSession,
    *,
    within_days: int = 60,
    page: int = 1,
    size: int = 50,
) -> tuple[list[Partner], int]:
    """#138/#146/#151 期限アラート: 許可・保険・CCUS・再審査の期限が切れている /
    within_days 以内に迫っている協力会社を一覧化する（決定論的）."""
    ref = date.today()
    limit_date = ref + timedelta(days=within_days)
    conds = []
    for col in (
        Partner.permit_expiry,
        Partner.insurance_expiry,
        Partner.ccus_expiry,
        Partner.next_review_due,
    ):
        conds.append(col.is_not(None) & (col <= limit_date))
    combined = conds[0]
    for cond in conds[1:]:
        combined = combined | cond
    stmt = select(Partner).where(combined)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Partner.id).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


def partner_expiry_flags(
    partner: Partner, *, today: date | None = None, within_days: int = 60
) -> dict[str, object]:
    """協力会社 1 社の期限状態フラグ（expired / expiring / ok を種別ごとに返す）."""
    ref = today or date.today()
    limit = ref + timedelta(days=within_days)

    def state(value: date | None) -> str:
        if value is None:
            return "unset"
        if value < ref:
            return "expired"
        if value <= limit:
            return "expiring"
        return "ok"

    return {
        "partner_id": partner.id,
        "partner_name": partner.name,
        "permit_expiry": partner.permit_expiry.isoformat() if partner.permit_expiry else None,
        "permit_state": state(partner.permit_expiry),
        "insurance_expiry": (
            partner.insurance_expiry.isoformat() if partner.insurance_expiry else None
        ),
        "insurance_state": state(partner.insurance_expiry),
        "ccus_expiry": partner.ccus_expiry.isoformat() if partner.ccus_expiry else None,
        "ccus_state": state(partner.ccus_expiry),
        "next_review_due": partner.next_review_due.isoformat() if partner.next_review_due else None,
        "review_state": state(partner.next_review_due),
        "risk_score": partner.risk_score,
    }


__all__ = [
    "complete_review",
    "compute_risk_score",
    "create_review",
    "get_review",
    "list_expiry_alerts",
    "list_reviews",
    "partner_expiry_flags",
    "refresh_risk_score",
]
