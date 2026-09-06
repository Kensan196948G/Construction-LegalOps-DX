"""独禁法・入札談合コンプライアンス業務サービス（Issue #122・ロードマップ #113〜#124）.

* #113/#114/#117/#118/#119 — ``antitrust_checker`` の決定論的ルールを実行し、
  ``antitrust_checks`` に永続化する。
* #115/#116/#121/#122/#123 — 「事前申請 → 承認 → 記録」ワークフロー
  （submitted → approved/rejected → completed、いつでも cancelled 可）。
* #120 — 一次情報コーパス検索（``evidence_lookup``）による参考回答生成
  （AI による断定的な法的判断は行わない）。
* #124 — コンプライアンス研修履歴の単純な登録・一覧。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.antitrust_compliance import (
    AntitrustCheck,
    AntitrustConsultation,
    AntitrustPriorApplication,
    ComplianceTraining,
)
from app.models.contract import Contract
from app.models.enums import (
    AntitrustApplicationStatus,
    AntitrustApplicationType,
    AntitrustCheckType,
)
from app.models.joint_venture import JointVenture
from app.services import antitrust_checker
from app.services.evidence_lookup import search_primary_sources

logger = structlog.get_logger(__name__)

CONSULTATION_DISCLAIMER = (
    "本回答は一次情報コーパスの検索結果に基づく参考情報です。個別事案への当てはめ・"
    "最終的な法的判断は法務担当者および顧問弁護士が行ってください。"
)

# 承認待ち（submitted）から遷移可能な決定
_DECISION_TRANSITIONS: dict[str, set[str]] = {
    AntitrustApplicationStatus.SUBMITTED.value: {
        AntitrustApplicationStatus.APPROVED.value,
        AntitrustApplicationStatus.REJECTED.value,
    },
}
# 完了報告（complete）が許可される状態
_COMPLETABLE_FROM = {AntitrustApplicationStatus.APPROVED.value}
# 取下げ（cancel）が許可される状態
_CANCELLABLE_FROM = {
    AntitrustApplicationStatus.SUBMITTED.value,
    AntitrustApplicationStatus.APPROVED.value,
}


async def _next_no(session: AsyncSession, *, model: Any, column: Any, prefix: str) -> str:
    """Generate a ``{prefix}-YYYY-NNNNNN`` sequential number scoped to the year."""
    year = datetime.now(UTC).strftime("%Y")
    full_prefix = f"{prefix}-{year}-"
    last = (
        (
            await session.execute(
                select(column)
                .where(column.like(f"{full_prefix}%"))
                .order_by(model.id.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{full_prefix}{next_seq:06d}"


# ---------------------------------------------------------------------------
# #113/#114/#117/#118/#119 決定論的ルールベースチェック
# ---------------------------------------------------------------------------


async def create_check(
    session: AsyncSession,
    *,
    actor_id: int | None,
    check_type: str,
    subject: str,
    context: dict[str, Any] | None = None,
    contract_id: int | None = None,
    jv_id: int | None = None,
    notes: str | None = None,
) -> AntitrustCheck:
    try:
        type_value = AntitrustCheckType(check_type).value
    except ValueError as exc:
        raise ValidationError(f"不正なチェック種別: {check_type!r}") from exc

    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    if jv_id is not None and await session.get(JointVenture, jv_id) is None:
        raise NotFoundError(f"JV が見つかりません（id={jv_id}）")

    ctx = context or {}
    findings = antitrust_checker.run_check(type_value, ctx)
    severity = antitrust_checker.overall_severity(findings)

    row = AntitrustCheck(
        check_no="",  # flush 後に採番
        check_type=type_value,
        severity=severity,
        subject=subject,
        contract_id=contract_id,
        jv_id=jv_id,
        input_context=ctx,
        findings=[f.to_dict() for f in findings],
        checked_at=datetime.now(UTC),
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.check_no = await _next_no(
        session, model=AntitrustCheck, column=AntitrustCheck.check_no, prefix="ATC"
    )
    await session.flush()
    await session.refresh(row)
    return row


async def get_check(session: AsyncSession, *, check_id: int) -> AntitrustCheck:
    row = await session.get(AntitrustCheck, check_id)
    if row is None:
        raise NotFoundError(f"チェック結果が見つかりません（id={check_id}）")
    return row


async def list_checks(
    session: AsyncSession,
    *,
    check_type: str | None = None,
    severity: str | None = None,
    contract_id: int | None = None,
    jv_id: int | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AntitrustCheck], int]:
    stmt = select(AntitrustCheck)
    if check_type is not None:
        stmt = stmt.where(AntitrustCheck.check_type == check_type)
    if severity is not None:
        stmt = stmt.where(AntitrustCheck.severity == severity)
    if contract_id is not None:
        stmt = stmt.where(AntitrustCheck.contract_id == contract_id)
    if jv_id is not None:
        stmt = stmt.where(AntitrustCheck.jv_id == jv_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AntitrustCheck.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


# ---------------------------------------------------------------------------
# #115/#116/#121/#122/#123 事前申請 → 承認 → 記録ワークフロー
# ---------------------------------------------------------------------------


async def create_application(
    session: AsyncSession,
    *,
    actor_id: int | None,
    application_type: str,
    title: str,
    counterparty_name: str | None = None,
    counterparty_organization: str | None = None,
    purpose: str | None = None,
    scheduled_at: datetime | None = None,
    location: str | None = None,
    amount_jpy: int | None = None,
    attendees: list[str] | None = None,
    contract_id: int | None = None,
    jv_id: int | None = None,
) -> AntitrustPriorApplication:
    try:
        type_value = AntitrustApplicationType(application_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な申請種別: {application_type!r}") from exc
    if amount_jpy is not None and amount_jpy < 0:
        raise ValidationError("amount_jpy は 0 以上としてください。")
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    if jv_id is not None and await session.get(JointVenture, jv_id) is None:
        raise NotFoundError(f"JV が見つかりません（id={jv_id}）")

    row = AntitrustPriorApplication(
        application_no="",  # flush 後に採番
        application_type=type_value,
        status=AntitrustApplicationStatus.SUBMITTED.value,
        title=title,
        counterparty_name=counterparty_name,
        counterparty_organization=counterparty_organization,
        purpose=purpose,
        scheduled_at=scheduled_at,
        location=location,
        amount_jpy=amount_jpy,
        attendees=attendees,
        contract_id=contract_id,
        jv_id=jv_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.application_no = await _next_no(
        session,
        model=AntitrustPriorApplication,
        column=AntitrustPriorApplication.application_no,
        prefix="AAP",
    )
    await session.flush()
    await session.refresh(row)
    return row


async def get_application(
    session: AsyncSession, *, application_id: int
) -> AntitrustPriorApplication:
    row = await session.get(AntitrustPriorApplication, application_id)
    if row is None:
        raise NotFoundError(f"申請が見つかりません（id={application_id}）")
    return row


async def list_applications(
    session: AsyncSession,
    *,
    application_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AntitrustPriorApplication], int]:
    stmt = select(AntitrustPriorApplication)
    if application_type is not None:
        stmt = stmt.where(AntitrustPriorApplication.application_type == application_type)
    if status is not None:
        try:
            stmt = stmt.where(
                AntitrustPriorApplication.status == AntitrustApplicationStatus(status).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AntitrustPriorApplication.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def decide_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int | None,
    decision: str,
    decision_note: str | None = None,
) -> AntitrustPriorApplication:
    """#115〜#123 承認 / 却下（submitted のみ）."""
    row = await get_application(session, application_id=application_id)
    try:
        decision_value = AntitrustApplicationStatus(decision).value
    except ValueError as exc:
        raise ValidationError(f"不正な決定: {decision!r}") from exc
    if decision_value not in (
        AntitrustApplicationStatus.APPROVED.value,
        AntitrustApplicationStatus.REJECTED.value,
    ):
        raise ValidationError("decision は approved / rejected のみです。")
    if decision_value not in _DECISION_TRANSITIONS.get(row.status, set()):
        raise ConflictError("承認・却下できるのは submitted（申請中）のみです。")

    row.status = decision_value
    row.approved_by = actor_id
    row.approved_at = datetime.now(UTC)
    row.decision_note = decision_note
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def complete_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int | None,
    outcome_note: str,
    occurred_at: datetime | None = None,
) -> AntitrustPriorApplication:
    """approved → completed（実施後の記録・議事メモを保存）."""
    row = await get_application(session, application_id=application_id)
    if row.status not in _COMPLETABLE_FROM:
        raise ConflictError("実施記録を登録できるのは approved（承認済み）のみです。")
    if not outcome_note or not outcome_note.strip():
        raise ValidationError("outcome_note は必須です。")

    row.status = AntitrustApplicationStatus.COMPLETED.value
    row.occurred_at = occurred_at or datetime.now(UTC)
    row.outcome_note = outcome_note
    row.reported_at = datetime.now(UTC)
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def cancel_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int | None,
    cancel_reason: str,
) -> AntitrustPriorApplication:
    row = await get_application(session, application_id=application_id)
    if row.status not in _CANCELLABLE_FROM:
        raise ConflictError("取下げできるのは submitted / approved のみです。")
    if not cancel_reason or not cancel_reason.strip():
        raise ValidationError("cancel_reason は必須です。")

    row.status = AntitrustApplicationStatus.CANCELLED.value
    row.cancel_reason = cancel_reason
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# #120 競争法 AI 相談（一次情報引用付きの参考回答）
# ---------------------------------------------------------------------------


def _format_consultation_answer(query: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return (
            f"ご質問「{query}」に直接該当する一次情報は社内コーパス内に見つかりませんでした。"
            "法務・コンプライアンス部門へ直接ご相談ください。"
        )
    lines = [f"ご質問「{query}」に関連する一次情報を検索しました。"]
    for i, hit in enumerate(hits, start=1):
        title = hit.get("title") or "(タイトル不明)"
        excerpt = hit.get("excerpt") or ""
        url = hit.get("source_url") or "(出典 URL 不明)"
        lines.append(f"{i}. {title} — {excerpt}\n   出典: {url}")
    lines.append("上記は一次情報コーパスの検索結果であり、個別事案への当てはめではありません。")
    return "\n".join(lines)


async def create_consultation(
    session: AsyncSession,
    *,
    actor_id: int | None,
    query_text: str,
    contract_id: int | None = None,
) -> AntitrustConsultation:
    """#120 質問文から一次情報コーパスを検索し、引用付きの参考回答を生成する."""
    if not query_text or not query_text.strip():
        raise ValidationError("query_text は必須です。")
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")

    hits = await search_primary_sources(session, query=query_text, limit=5)
    citations = [h.to_dict() for h in hits]
    answer = _format_consultation_answer(query_text, citations)

    row = AntitrustConsultation(
        query_text=query_text,
        answer_text=answer,
        citations=citations,
        contract_id=contract_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_consultation(session: AsyncSession, *, consultation_id: int) -> AntitrustConsultation:
    row = await session.get(AntitrustConsultation, consultation_id)
    if row is None:
        raise NotFoundError(f"相談履歴が見つかりません（id={consultation_id}）")
    return row


async def list_consultations(
    session: AsyncSession,
    *,
    contract_id: int | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AntitrustConsultation], int]:
    stmt = select(AntitrustConsultation)
    if contract_id is not None:
        stmt = stmt.where(AntitrustConsultation.contract_id == contract_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AntitrustConsultation.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


# ---------------------------------------------------------------------------
# #124 コンプライアンス研修履歴
# ---------------------------------------------------------------------------


async def create_training(
    session: AsyncSession,
    *,
    actor_id: int | None,
    training_title: str,
    completed_at: date,
    user_id: int | None = None,
    attendee_name: str | None = None,
    category: str = "antitrust",
    score: int | None = None,
    certificate_url: str | None = None,
    notes: str | None = None,
) -> ComplianceTraining:
    if user_id is None and not (attendee_name and attendee_name.strip()):
        raise ValidationError("user_id または attendee_name のいずれかが必要です。")
    if score is not None and not (0 <= score <= 100):
        raise ValidationError("score は 0〜100 の範囲としてください。")

    row = ComplianceTraining(
        user_id=user_id,
        attendee_name=attendee_name,
        training_title=training_title,
        category=category,
        completed_at=completed_at,
        score=score,
        certificate_url=certificate_url,
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_trainings(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[ComplianceTraining], int]:
    stmt = select(ComplianceTraining)
    if user_id is not None:
        stmt = stmt.where(ComplianceTraining.user_id == user_id)
    if category is not None:
        stmt = stmt.where(ComplianceTraining.category == category)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(ComplianceTraining.completed_at.desc(), ComplianceTraining.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


__all__ = [
    "CONSULTATION_DISCLAIMER",
    "cancel_application",
    "complete_application",
    "create_application",
    "create_check",
    "create_consultation",
    "create_training",
    "decide_application",
    "get_application",
    "get_check",
    "get_consultation",
    "list_applications",
    "list_checks",
    "list_consultations",
    "list_trainings",
]
