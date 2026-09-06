"""紛争・クレーム管理高度化サービス（ロードマップ #97〜#112 / Issue #121）.

すべての判定・生成ロジックは決定論的なルールエンジン／テンプレート処理として
実装し、AI は使用しない（最終的な法的判断は行わず、利用者の確認・編集を前提と
した草案・アラート・スコアの提示に留める）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.deps import CurrentUser
from app.models.dispute import Dispute
from app.models.dispute_ext import (
    DisputeArgumentPosition,
    DisputeDelayEvent,
    DisputeProceedingStage,
    DisputeSettlementOption,
)
from app.models.enums import (
    DisputeEotStatus,
    DisputeProceedingStageStatus,
)

# ---------------------------------------------------------------------------
# 共通ヘルパー
# ---------------------------------------------------------------------------


async def get_dispute_full(
    session: AsyncSession, *, dispute_id: int, viewer: CurrentUser
) -> Dispute:
    """関連（timeline / evidence / delay_events）をロード済みの Dispute を返す。

    Issue #127/#129: 案件（契約）ACL に基づくアプリ層の認可チェックを適用する
    （`app.services.dispute_service.ensure_dispute_visible` と同じ判定）。
    """
    from app.services.dispute_service import ensure_dispute_visible

    stmt = (
        select(Dispute)
        .where(Dispute.id == dispute_id, Dispute.deleted_at.is_(None))
        .options(
            selectinload(Dispute.timeline),
            selectinload(Dispute.evidence),
            selectinload(Dispute.delay_events),
        )
        # 同一セッション内で複数回呼ばれても（例: スコア算出 → その後に遅延事象を
        # 追加 → Chronology 生成）関連の最新状態を確実に反映するため、identity map
        # のキャッシュに関わらず常に再読込する。
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"紛争案件が見つかりません（id={dispute_id}）")
    await ensure_dispute_visible(session, dispute=row, viewer=viewer)
    return row


async def _get_dispute(session: AsyncSession, *, dispute_id: int) -> Dispute:
    row = await session.get(Dispute, dispute_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(f"紛争案件が見つかりません（id={dispute_id}）")
    return row


# ---------------------------------------------------------------------------
# #100〜#104 遅延事象台帳・原因分類・追加費用・損害額・EOT
# ---------------------------------------------------------------------------


def compute_damage_amount(
    *,
    delay_days: int,
    additional_cost_jpy: int | None,
    daily_overhead_rate_jpy: int | None,
) -> int:
    """#103 損害額を決定論的に算定する（追加費用 ＋ 遅延日数 × 日額間接費）."""
    base = additional_cost_jpy or 0
    if daily_overhead_rate_jpy and delay_days > 0:
        base += daily_overhead_rate_jpy * delay_days
    return base


async def add_delay_event(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    data: dict[str, Any],
) -> DisputeDelayEvent:
    """#100 遅延事象を登録する（#101 原因分類・#102 追加費用・#103 損害額を含む）."""
    await _get_dispute(session, dispute_id=dispute_id)
    occurred_from: date = data["occurred_from"]
    occurred_to: date | None = data.get("occurred_to")
    if occurred_to is not None and occurred_to < occurred_from:
        raise ValidationError("終了日は開始日以降にしてください。")
    delay_days = int(data.get("delay_days") or 0)

    damage_amount = data.get("damage_amount_jpy")
    if damage_amount is None:
        damage_amount = compute_damage_amount(
            delay_days=delay_days,
            additional_cost_jpy=data.get("additional_cost_jpy"),
            daily_overhead_rate_jpy=data.get("daily_overhead_rate_jpy"),
        )

    row = DisputeDelayEvent(
        dispute_id=dispute_id,
        cause_category=data["cause_category"],
        title=data["title"],
        description=data.get("description"),
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        delay_days=delay_days,
        responsible_party=data.get("responsible_party"),
        additional_cost_jpy=data.get("additional_cost_jpy"),
        damage_amount_jpy=damage_amount,
        eot_days_requested=data.get("eot_days_requested"),
        eot_status=DisputeEotStatus.PENDING.value,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_delay_events(session: AsyncSession, *, dispute_id: int) -> list[DisputeDelayEvent]:
    await _get_dispute(session, dispute_id=dispute_id)
    stmt = (
        select(DisputeDelayEvent)
        .where(DisputeDelayEvent.dispute_id == dispute_id)
        .order_by(DisputeDelayEvent.occurred_from)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_delay_event(session: AsyncSession, *, delay_event_id: int) -> DisputeDelayEvent:
    row = await session.get(DisputeDelayEvent, delay_event_id)
    if row is None:
        raise NotFoundError(f"遅延事象が見つかりません（id={delay_event_id}）")
    return row


async def update_delay_event_eot(
    session: AsyncSession,
    *,
    delay_event_id: int,
    actor_id: int | None,
    eot_status: str,
    eot_days_granted: int | None,
    eot_note: str | None,
) -> DisputeDelayEvent:
    """#104 EOT／工期延長の判定を記録する（pending からのみ遷移）."""
    row = await get_delay_event(session, delay_event_id=delay_event_id)
    if row.eot_status != DisputeEotStatus.PENDING.value:
        raise ConflictError("EOT 判定は pending（未判定）からのみ更新できます。")
    try:
        status_value = DisputeEotStatus(eot_status)
    except ValueError as exc:
        raise ValidationError(f"不正な EOT 判定: {eot_status!r}") from exc
    if status_value == DisputeEotStatus.PENDING:
        raise ValidationError("判定結果は approved / partial / rejected のいずれかです。")
    if status_value in (DisputeEotStatus.APPROVED, DisputeEotStatus.PARTIAL) and (
        eot_days_granted is None or eot_days_granted < 0
    ):
        raise ValidationError("認容日数（eot_days_granted）を 0 以上で指定してください。")

    row.eot_status = status_value.value
    row.eot_days_granted = 0 if status_value == DisputeEotStatus.REJECTED else eot_days_granted
    row.eot_decided_at = datetime.now(UTC)
    row.eot_decided_by = actor_id
    row.eot_note = eot_note
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def delay_summary(session: AsyncSession, *, dispute_id: int) -> dict[str, Any]:
    """#101 原因別分類・#102 追加費用積上げ・#103 損害額の集計を返す。"""
    events = await list_delay_events(session, dispute_id=dispute_id)
    by_cause: dict[str, dict[str, int]] = {}
    total_delay_days = 0
    total_additional_cost = 0
    total_damage = 0
    total_eot_granted = 0
    for ev in events:
        bucket = by_cause.setdefault(
            ev.cause_category,
            {
                "count": 0,
                "total_delay_days": 0,
                "total_additional_cost_jpy": 0,
                "total_damage_amount_jpy": 0,
            },
        )
        bucket["count"] += 1
        bucket["total_delay_days"] += ev.delay_days
        bucket["total_additional_cost_jpy"] += ev.additional_cost_jpy or 0
        bucket["total_damage_amount_jpy"] += ev.damage_amount_jpy or 0
        total_delay_days += ev.delay_days
        total_additional_cost += ev.additional_cost_jpy or 0
        total_damage += ev.damage_amount_jpy or 0
        total_eot_granted += ev.eot_days_granted or 0

    return {
        "dispute_id": dispute_id,
        "by_cause": [
            {"cause_category": cause, **stats} for cause, stats in sorted(by_cause.items())
        ],
        "total_delay_days": total_delay_days,
        "total_additional_cost_jpy": total_additional_cost,
        "total_damage_amount_jpy": total_damage,
        "total_eot_days_granted": total_eot_granted,
    }


# ---------------------------------------------------------------------------
# #97 Claim Notice Generator（決定論的テンプレート処理・AI 不使用）
# ---------------------------------------------------------------------------

_DISPUTE_TYPE_LABELS = {
    "claim": "クレーム",
    "defect": "瑕疵",
    "delay": "遅延",
    "payment": "支払",
    "labor": "労務",
    "accident": "事故",
    "other": "その他",
}


def generate_claim_notice(
    dispute: Dispute,
    *,
    sender_name: str,
    recipient_name: str | None = None,
    notice_date: date | None = None,
    extra_note: str | None = None,
) -> dict[str, Any]:
    """#97 クレーム通知書を決定論的テンプレートで生成する。"""
    if not sender_name.strip():
        raise ValidationError("差出人名は必須です。")
    notice_date = notice_date or date.today()
    recipient = (recipient_name or dispute.counterparty or "相手方").strip()
    type_label = _DISPUTE_TYPE_LABELS.get(dispute.dispute_type, dispute.dispute_type)

    lines: list[str] = [
        "通知書",
        "",
        f"通知日: {notice_date.isoformat()}",
        f"宛先: {recipient} 御中",
        f"差出人: {sender_name.strip()}",
        "",
        f"件名: {dispute.title}（管理番号: {dispute.dispute_no} / 種別: {type_label}）",
        "",
        "下記の件につき、貴社に通知いたします。",
    ]
    if dispute.description:
        lines.append(f"経緯・内容: {dispute.description}")
    if dispute.amount_claimed_jpy is not None:
        lines.append(f"請求金額（現時点）: {dispute.amount_claimed_jpy:,} 円")
    if dispute.notice_deadline is not None:
        lines.append(f"通知期限: {dispute.notice_deadline.isoformat()}")
    if dispute.statute_limitations_date is not None:
        lines.append(f"消滅時効日（参考）: {dispute.statute_limitations_date.isoformat()}")
    lines.append("")
    lines.append(
        "本通知書は本件に係る権利保全のための一次通知であり、法的な最終判断を"
        "示すものではありません。詳細は追ってご連絡いたします。"
    )
    if extra_note:
        lines.append("")
        lines.append(f"備考: {extra_note.strip()}")

    return {
        "dispute_id": dispute.id,
        "subject": f"{dispute.title}（{type_label}）に関する通知",
        "recipient": recipient,
        "sender": sender_name.strip(),
        "notice_date": notice_date,
        "notice_deadline": dispute.notice_deadline,
        "statute_limitations_date": dispute.statute_limitations_date,
        "formatted_text": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# #98 通知期限自動判定（決定論的既定日数テーブル）
# ---------------------------------------------------------------------------

_DEFAULT_NOTICE_PERIOD_DAYS: dict[str, int] = {
    "claim": 14,
    "delay": 21,
    "defect": 30,
    "payment": 30,
    "labor": 14,
    "accident": 7,
    "other": 14,
}


def auto_judge_notice_deadline(
    *, dispute_type: str, event_date: date, override_days: int | None = None
) -> dict[str, Any]:
    """#98 通知期限を決定論的に判定する（契約約款上の通知期間の既定値テーブル）."""
    days = (
        override_days
        if override_days is not None
        else _DEFAULT_NOTICE_PERIOD_DAYS.get(dispute_type, 14)
    )
    if days <= 0:
        raise ValidationError("通知期間（日数）は正の整数で指定してください。")
    deadline = event_date + timedelta(days=days)
    return {
        "dispute_type": dispute_type,
        "event_date": event_date,
        "notice_period_days": days,
        "notice_deadline": deadline,
    }


async def apply_notice_deadline_auto_judge(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    event_date: date,
    override_days: int | None,
    apply: bool,
) -> dict[str, Any]:
    dispute = await _get_dispute(session, dispute_id=dispute_id)
    result = auto_judge_notice_deadline(
        dispute_type=dispute.dispute_type, event_date=event_date, override_days=override_days
    )
    if apply:
        dispute.notice_deadline = result["notice_deadline"]
        dispute.updated_by = actor_id
        await session.flush()
        await session.refresh(dispute)
    return {
        "dispute_id": dispute_id,
        "dispute_type": result["dispute_type"],
        "event_date": result["event_date"],
        "notice_period_days": result["notice_period_days"],
        "notice_deadline": result["notice_deadline"],
        "applied": apply,
    }


# ---------------------------------------------------------------------------
# #99 Time Bar 警告 / #112 消滅時効タイマー
# ---------------------------------------------------------------------------

_TIME_BAR_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (30, "critical"),
    (90, "warning"),
    (180, "info"),
)

_SEVERITY_RANK = {"expired": 0, "critical": 1, "warning": 2, "info": 3}


def _days_remaining(target: date | None, *, today: date) -> int | None:
    if target is None:
        return None
    return (target - today).days


def _severity_for_days(days_remaining: int | None) -> str | None:
    if days_remaining is None:
        return None
    if days_remaining < 0:
        return "expired"
    for threshold, severity in _TIME_BAR_THRESHOLDS:
        if days_remaining <= threshold:
            return severity
    return None


def _overall_severity(*severities: str | None) -> str | None:
    ranked = [s for s in severities if s is not None]
    if not ranked:
        return None
    return min(ranked, key=lambda s: _SEVERITY_RANK[s])


def dispute_time_bar_status(dispute: Dispute, *, today: date | None = None) -> dict[str, Any]:
    """#99/#112 単一案件の消滅時効・通知期限タイマー状態を算出する。"""
    ref = today or date.today()
    statute_days = _days_remaining(dispute.statute_limitations_date, today=ref)
    notice_days = _days_remaining(dispute.notice_deadline, today=ref)
    severity = _overall_severity(_severity_for_days(statute_days), _severity_for_days(notice_days))
    return {
        "dispute_id": dispute.id,
        "dispute_no": dispute.dispute_no,
        "title": dispute.title,
        "status": dispute.status,
        "statute_limitations_date": dispute.statute_limitations_date,
        "statute_days_remaining": statute_days,
        "notice_deadline": dispute.notice_deadline,
        "notice_days_remaining": notice_days,
        "severity": severity,
    }


async def list_time_bar_alerts(
    session: AsyncSession, *, within_days: int = 180
) -> list[dict[str, Any]]:
    """#99/#112 消滅時効・通知期限が迫っている（または経過した）未解決案件を返す。"""
    stmt = select(Dispute).where(
        Dispute.deleted_at.is_(None),
        Dispute.status.in_(("open", "investigating", "escalated")),
        (Dispute.statute_limitations_date.is_not(None) | Dispute.notice_deadline.is_not(None)),
    )
    rows = list((await session.execute(stmt)).scalars().all())
    today = date.today()
    alerts = [dispute_time_bar_status(row, today=today) for row in rows]
    alerts = [a for a in alerts if a["severity"] is not None]
    alerts.sort(
        key=lambda a: (
            _SEVERITY_RANK[a["severity"]],
            min(
                d
                for d in (a["statute_days_remaining"], a["notice_days_remaining"])
                if d is not None
            ),
        )
    )
    return alerts


# ---------------------------------------------------------------------------
# #105 証拠充足度スコア / #106 証拠不足検知（ルールベース・AI 不使用）
# ---------------------------------------------------------------------------

_REQUIRED_EVIDENCE_BY_TYPE: dict[str, set[str]] = {
    "claim": {"contract", "email", "daily_report"},
    "defect": {"photo", "daily_report", "other"},
    "delay": {"daily_report", "photo", "email"},
    "payment": {"contract", "email"},
    "labor": {"contract", "daily_report"},
    "accident": {"photo", "daily_report", "minutes"},
    "other": {"contract"},
}


def evidence_sufficiency_score(dispute: Dispute) -> dict[str, Any]:
    """#105 証拠充足度スコア・#106 証拠不足検知をルールベースで算出する。

    AI は使用しない。案件種別ごとの必須証拠カテゴリの充足率（80 点満点）と、
    保全（preserved）済み比率のボーナス（20 点満点）で 0〜100 点を算定する。
    """
    required = _REQUIRED_EVIDENCE_BY_TYPE.get(dispute.dispute_type, {"contract"})
    present_types = {e.evidence_type for e in dispute.evidence}
    preserved_types = {e.evidence_type for e in dispute.evidence if e.preserved}
    missing = sorted(required - present_types)
    coverage = len(required & present_types) / len(required) if required else 1.0
    preservation_bonus = 0.0
    if present_types:
        preservation_bonus = (len(preserved_types) / len(present_types)) * 20
    score = max(0, min(100, round(coverage * 80 + preservation_bonus)))

    recommendations = [
        f"『{t}』種別の証拠が未登録です（{dispute.dispute_type} 案件で必須と判定）。"
        for t in missing
    ]
    unpreserved = sorted(present_types - preserved_types)
    if unpreserved:
        recommendations.append(
            "保全（preserved）未設定の証拠があります。Legal Hold 対象か確認してください: "
            + "、".join(unpreserved)
        )
    if not dispute.evidence:
        recommendations.append("証拠が 1 件も登録されていません。至急、収集・記録してください。")

    return {
        "dispute_id": dispute.id,
        "score": score,
        "required_types": sorted(required),
        "present_types": sorted(present_types),
        "missing_types": missing,
        "unpreserved_types": unpreserved,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# #107/#108 Claim Chronology 自動生成（時系列統合）
# ---------------------------------------------------------------------------


def _to_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.combine(value, datetime.min.time(), tzinfo=UTC)


def build_chronology(dispute: Dispute) -> list[dict[str, Any]]:
    """#107/#108 タイムライン・証拠・遅延事象を時系列に統合した Chronology を生成する。"""
    entries: list[dict[str, Any]] = []
    for tl in dispute.timeline:
        entries.append(
            {
                "source_type": f"timeline:{tl.event_type}",
                "occurred_at": _to_datetime(tl.occurred_at),
                "title": tl.event_type,
                "description": tl.description,
                "ref_id": tl.id,
                "estimated": False,
            }
        )
    for ev in dispute.evidence:
        occurred = ev.occurred_at
        estimated = occurred is None
        occurred_at = (
            _to_datetime(occurred) if occurred is not None else _to_datetime(ev.created_at)
        )
        entries.append(
            {
                "source_type": f"evidence:{ev.evidence_type}",
                "occurred_at": occurred_at,
                "title": f"証拠: {ev.evidence_type}",
                "description": ev.description,
                "ref_id": ev.id,
                "estimated": estimated,
            }
        )
    for de in dispute.delay_events:
        entries.append(
            {
                "source_type": f"delay_event:{de.cause_category}",
                "occurred_at": _to_datetime(de.occurred_from),
                "title": de.title,
                "description": de.description,
                "ref_id": de.id,
                "estimated": False,
            }
        )
    entries.sort(key=lambda e: e["occurred_at"])
    return entries


# ---------------------------------------------------------------------------
# #109 主張・反論マトリクス
# ---------------------------------------------------------------------------


async def add_argument_position(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    data: dict[str, Any],
) -> DisputeArgumentPosition:
    await _get_dispute(session, dispute_id=dispute_id)
    row = DisputeArgumentPosition(
        dispute_id=dispute_id,
        issue_no=int(data.get("issue_no") or 1),
        issue_title=data["issue_title"],
        party=data["party"],
        stance=data["stance"],
        content=data["content"],
        evidence_refs=list(data.get("evidence_refs") or []),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_argument_positions(
    session: AsyncSession, *, dispute_id: int
) -> list[DisputeArgumentPosition]:
    await _get_dispute(session, dispute_id=dispute_id)
    stmt = (
        select(DisputeArgumentPosition)
        .where(DisputeArgumentPosition.dispute_id == dispute_id)
        .order_by(DisputeArgumentPosition.issue_no, DisputeArgumentPosition.id)
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# #110 和解案比較
# ---------------------------------------------------------------------------


def compute_expected_value(
    *, settlement_amount_jpy: int | None, probability_score: int | None
) -> int | None:
    if settlement_amount_jpy is None or probability_score is None:
        return None
    return round(settlement_amount_jpy * probability_score / 100)


async def add_settlement_option(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    data: dict[str, Any],
) -> DisputeSettlementOption:
    await _get_dispute(session, dispute_id=dispute_id)
    row = DisputeSettlementOption(
        dispute_id=dispute_id,
        option_no=int(data.get("option_no") or 1),
        title=data["title"],
        settlement_amount_jpy=data.get("settlement_amount_jpy"),
        payment_terms=data.get("payment_terms"),
        pros=data.get("pros"),
        cons=data.get("cons"),
        probability_score=data.get("probability_score"),
        expected_value_jpy=compute_expected_value(
            settlement_amount_jpy=data.get("settlement_amount_jpy"),
            probability_score=data.get("probability_score"),
        ),
        notes=data.get("notes"),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_settlement_option(
    session: AsyncSession, *, option_id: int
) -> DisputeSettlementOption:
    row = await session.get(DisputeSettlementOption, option_id)
    if row is None:
        raise NotFoundError(f"和解案が見つかりません（id={option_id}）")
    return row


async def update_settlement_option(
    session: AsyncSession,
    *,
    option_id: int,
    actor_id: int | None,
    data: dict[str, Any],
) -> DisputeSettlementOption:
    row = await get_settlement_option(session, option_id=option_id)
    for field in (
        "title",
        "settlement_amount_jpy",
        "payment_terms",
        "pros",
        "cons",
        "probability_score",
        "status",
        "notes",
    ):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])
    row.expected_value_jpy = compute_expected_value(
        settlement_amount_jpy=row.settlement_amount_jpy,
        probability_score=row.probability_score,
    )
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def list_settlement_options(
    session: AsyncSession, *, dispute_id: int
) -> list[DisputeSettlementOption]:
    await _get_dispute(session, dispute_id=dispute_id)
    stmt = (
        select(DisputeSettlementOption)
        .where(DisputeSettlementOption.dispute_id == dispute_id)
        .order_by(DisputeSettlementOption.option_no)
    )
    return list((await session.execute(stmt)).scalars().all())


async def compare_settlement_options(
    session: AsyncSession, *, dispute_id: int
) -> list[dict[str, Any]]:
    """#110 和解案を期待値（金額 × 確度）順に比較し、最有力案を推奨としてマークする。"""
    options = await list_settlement_options(session, dispute_id=dispute_id)
    ranked = sorted(
        options,
        key=lambda o: (o.expected_value_jpy is None, -(o.expected_value_jpy or 0)),
    )
    active_statuses = {"draft", "proposed"}
    recommended_id = next(
        (o.id for o in ranked if o.status in active_statuses and o.expected_value_jpy is not None),
        None,
    )
    return [
        {
            "id": o.id,
            "option_no": o.option_no,
            "title": o.title,
            "settlement_amount_jpy": o.settlement_amount_jpy,
            "probability_score": o.probability_score,
            "expected_value_jpy": o.expected_value_jpy,
            "status": o.status,
            "recommended": o.id == recommended_id,
        }
        for o in ranked
    ]


# ---------------------------------------------------------------------------
# #111 訴訟・ADR ステージ管理
# ---------------------------------------------------------------------------


async def add_proceeding_stage(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor_id: int | None,
    data: dict[str, Any],
) -> DisputeProceedingStage:
    """#111 新しいステージを追加する（直前の進行中ステージは自動的に完了させる）."""
    await _get_dispute(session, dispute_id=dispute_id)
    started_at: date = data["started_at"]
    ended_at: date | None = data.get("ended_at")
    if ended_at is not None and ended_at < started_at:
        raise ValidationError("終了日は開始日以降にしてください。")

    stmt = select(DisputeProceedingStage).where(
        DisputeProceedingStage.dispute_id == dispute_id,
        DisputeProceedingStage.status == DisputeProceedingStageStatus.ACTIVE.value,
    )
    active_stages = list((await session.execute(stmt)).scalars().all())
    for stage in active_stages:
        stage.status = DisputeProceedingStageStatus.COMPLETED.value
        if stage.ended_at is None:
            # 遡及登録（新ステージの started_at が既存ステージの started_at より前）
            # で ended_at < started_at という不整合レコードを作らないよう、
            # 既存ステージ自身の started_at を下限にする。
            stage.ended_at = max(started_at, stage.started_at)
        stage.updated_by = actor_id

    row = DisputeProceedingStage(
        dispute_id=dispute_id,
        stage=data["stage"],
        status=(
            DisputeProceedingStageStatus.COMPLETED.value
            if ended_at is not None
            else DisputeProceedingStageStatus.ACTIVE.value
        ),
        started_at=started_at,
        ended_at=ended_at,
        forum=data.get("forum"),
        notes=data.get("notes"),
        extra_data={},
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_proceeding_stages(
    session: AsyncSession, *, dispute_id: int
) -> list[DisputeProceedingStage]:
    await _get_dispute(session, dispute_id=dispute_id)
    stmt = (
        select(DisputeProceedingStage)
        .where(DisputeProceedingStage.dispute_id == dispute_id)
        .order_by(DisputeProceedingStage.started_at, DisputeProceedingStage.id)
    )
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "add_argument_position",
    "add_delay_event",
    "add_proceeding_stage",
    "add_settlement_option",
    "apply_notice_deadline_auto_judge",
    "auto_judge_notice_deadline",
    "build_chronology",
    "compare_settlement_options",
    "compute_damage_amount",
    "compute_expected_value",
    "delay_summary",
    "dispute_time_bar_status",
    "evidence_sufficiency_score",
    "generate_claim_notice",
    "get_delay_event",
    "get_dispute_full",
    "get_settlement_option",
    "list_argument_positions",
    "list_delay_events",
    "list_proceeding_stages",
    "list_settlement_options",
    "list_time_bar_alerts",
    "update_delay_event_eot",
    "update_settlement_option",
]
