"""紛争・クレーム管理高度化サービスの単体テスト（ロードマップ #97〜#112 / Issue #121）."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.dispute import Dispute, DisputeEvidence, DisputeTimelineEvent
from app.models.dispute_ext import DisputeDelayEvent
from app.services import dispute_ext_service as svc


async def _seed_dispute(db_session, **overrides) -> Dispute:
    defaults: dict[str, object] = {
        "dispute_no": f"D-{uuid4().hex[:10].upper()}",
        "dispute_type": "delay",
        "title": "遅延紛争（テスト）",
        "status": "open",
        "priority": "中",
    }
    defaults.update(overrides)
    row = Dispute(**defaults)
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 純粋関数（決定論的ルール・AI 不使用）
# ---------------------------------------------------------------------------


def test_compute_damage_amount_uses_daily_rate() -> None:
    amount = svc.compute_damage_amount(
        delay_days=10, additional_cost_jpy=100_000, daily_overhead_rate_jpy=5_000
    )
    assert amount == 100_000 + 10 * 5_000


def test_compute_damage_amount_without_daily_rate() -> None:
    amount = svc.compute_damage_amount(
        delay_days=10, additional_cost_jpy=100_000, daily_overhead_rate_jpy=None
    )
    assert amount == 100_000


def test_auto_judge_notice_deadline_defaults_by_type() -> None:
    result = svc.auto_judge_notice_deadline(dispute_type="delay", event_date=date(2026, 1, 1))
    assert result["notice_period_days"] == 21
    assert result["notice_deadline"] == date(2026, 1, 22)


def test_auto_judge_notice_deadline_override() -> None:
    result = svc.auto_judge_notice_deadline(
        dispute_type="claim", event_date=date(2026, 1, 1), override_days=5
    )
    assert result["notice_period_days"] == 5
    assert result["notice_deadline"] == date(2026, 1, 6)


def test_auto_judge_notice_deadline_rejects_nonpositive_days() -> None:
    with pytest.raises(ValidationError):
        svc.auto_judge_notice_deadline(
            dispute_type="claim", event_date=date(2026, 1, 1), override_days=0
        )


def test_generate_claim_notice_includes_key_fields() -> None:
    dispute = Dispute(
        id=1,
        dispute_no="D-TEST0001",
        dispute_type="claim",
        title="追加工事費請求",
        status="open",
        priority="高",
        counterparty="テスト下請株式会社",
        amount_claimed_jpy=5_000_000,
        notice_deadline=date(2026, 3, 1),
        statute_limitations_date=date(2027, 1, 1),
    )
    result = svc.generate_claim_notice(
        dispute, sender_name="テスト元請株式会社", notice_date=date(2026, 2, 1)
    )
    assert result["recipient"] == "テスト下請株式会社"
    assert "D-TEST0001" in result["formatted_text"]
    assert "5,000,000 円" in result["formatted_text"]
    assert result["notice_deadline"] == date(2026, 3, 1)


def test_generate_claim_notice_requires_sender_name() -> None:
    dispute = Dispute(id=1, dispute_no="D-X", dispute_type="claim", title="t", status="open")
    with pytest.raises(ValidationError):
        svc.generate_claim_notice(dispute, sender_name="   ")


def test_dispute_time_bar_status_severity_levels() -> None:
    today = date(2026, 6, 1)
    critical = Dispute(
        id=1,
        dispute_no="D-1",
        dispute_type="claim",
        title="t",
        status="open",
        statute_limitations_date=today + timedelta(days=10),
    )
    result = svc.dispute_time_bar_status(critical, today=today)
    assert result["severity"] == "critical"

    expired = Dispute(
        id=2,
        dispute_no="D-2",
        dispute_type="claim",
        title="t",
        status="open",
        notice_deadline=today - timedelta(days=1),
    )
    result_expired = svc.dispute_time_bar_status(expired, today=today)
    assert result_expired["severity"] == "expired"

    safe = Dispute(
        id=3,
        dispute_no="D-3",
        dispute_type="claim",
        title="t",
        status="open",
        statute_limitations_date=today + timedelta(days=400),
    )
    result_safe = svc.dispute_time_bar_status(safe, today=today)
    assert result_safe["severity"] is None


def test_evidence_sufficiency_score_flags_missing_and_unpreserved() -> None:
    dispute = Dispute(id=1, dispute_no="D-1", dispute_type="claim", title="t", status="open")
    dispute.evidence = [
        DisputeEvidence(evidence_type="contract", preserved=True),
        DisputeEvidence(evidence_type="email", preserved=False),
    ]
    result = svc.evidence_sufficiency_score(dispute)
    # claim の必須は {contract, email, daily_report} → daily_report が不足
    assert "daily_report" in result["missing_types"]
    assert "email" in result["unpreserved_types"]
    assert 0 <= result["score"] <= 100
    assert result["recommendations"]  # 不足・未保全のいずれかで推奨が生成される


def test_evidence_sufficiency_score_full_coverage_scores_high() -> None:
    dispute = Dispute(id=1, dispute_no="D-1", dispute_type="claim", title="t", status="open")
    dispute.evidence = [
        DisputeEvidence(evidence_type="contract", preserved=True),
        DisputeEvidence(evidence_type="email", preserved=True),
        DisputeEvidence(evidence_type="daily_report", preserved=True),
    ]
    result = svc.evidence_sufficiency_score(dispute)
    assert result["score"] == 100
    assert result["missing_types"] == []
    assert result["unpreserved_types"] == []


def test_build_chronology_sorts_across_sources() -> None:
    dispute = Dispute(id=1, dispute_no="D-1", dispute_type="delay", title="t", status="open")
    dispute.timeline = [
        DisputeTimelineEvent(
            id=1,
            event_type="notice",
            description="通知",
            occurred_at=datetime(2026, 2, 1, 0, 0, tzinfo=UTC),
        )
    ]
    dispute.evidence = [DisputeEvidence(id=1, evidence_type="photo", occurred_at=date(2026, 1, 15))]
    dispute.delay_events = [
        DisputeDelayEvent(
            id=1,
            cause_category="weather",
            title="降雨による遅延",
            occurred_from=date(2026, 1, 1),
        )
    ]
    entries = svc.build_chronology(dispute)
    assert [e["source_type"].split(":")[0] for e in entries] == [
        "delay_event",
        "evidence",
        "timeline",
    ]


def test_compute_expected_value() -> None:
    assert (
        svc.compute_expected_value(settlement_amount_jpy=1_000_000, probability_score=70) == 700_000
    )
    assert svc.compute_expected_value(settlement_amount_jpy=None, probability_score=70) is None
    assert (
        svc.compute_expected_value(settlement_amount_jpy=1_000_000, probability_score=None) is None
    )


# ---------------------------------------------------------------------------
# DB を伴うサービス関数
# ---------------------------------------------------------------------------


async def test_add_and_list_delay_events_and_summary(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    await svc.add_delay_event(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "cause_category": "owner_caused",
            "title": "設計変更による遅延",
            "occurred_from": date(2026, 1, 1),
            "occurred_to": date(2026, 1, 10),
            "delay_days": 9,
            "additional_cost_jpy": 300_000,
            "daily_overhead_rate_jpy": None,
        },
    )
    await svc.add_delay_event(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "cause_category": "weather",
            "title": "台風による遅延",
            "occurred_from": date(2026, 2, 1),
            "delay_days": 3,
            "daily_overhead_rate_jpy": 10_000,
        },
    )
    events = await svc.list_delay_events(db_session, dispute_id=dispute.id)
    assert len(events) == 2
    assert events[1].damage_amount_jpy == 3 * 10_000  # daily_rate 経由の自動算定

    summary = await svc.delay_summary(db_session, dispute_id=dispute.id)
    assert summary["total_delay_days"] == 12
    assert summary["total_additional_cost_jpy"] == 300_000
    assert len(summary["by_cause"]) == 2


async def test_add_delay_event_rejects_invalid_date_range(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    with pytest.raises(ValidationError):
        await svc.add_delay_event(
            db_session,
            dispute_id=dispute.id,
            actor_id=None,
            data={
                "cause_category": "other",
                "title": "不正な期間",
                "occurred_from": date(2026, 2, 1),
                "occurred_to": date(2026, 1, 1),
            },
        )


async def test_add_delay_event_dispute_not_found(db_session) -> None:
    with pytest.raises(NotFoundError):
        await svc.add_delay_event(
            db_session,
            dispute_id=999_999,
            actor_id=None,
            data={
                "cause_category": "other",
                "title": "x",
                "occurred_from": date(2026, 1, 1),
            },
        )


async def test_update_delay_event_eot_lifecycle(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    row = await svc.add_delay_event(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "cause_category": "owner_caused",
            "title": "EOT テスト",
            "occurred_from": date(2026, 1, 1),
            "eot_days_requested": 10,
        },
    )
    updated = await svc.update_delay_event_eot(
        db_session,
        delay_event_id=row.id,
        actor_id=None,
        eot_status="partial",
        eot_days_granted=5,
        eot_note="一部認容（テスト）",
    )
    assert updated.eot_status == "partial"
    assert updated.eot_days_granted == 5

    with pytest.raises(ConflictError):
        await svc.update_delay_event_eot(
            db_session,
            delay_event_id=row.id,
            actor_id=None,
            eot_status="approved",
            eot_days_granted=10,
            eot_note=None,
        )


async def test_update_delay_event_eot_rejects_missing_days(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    row = await svc.add_delay_event(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={"cause_category": "other", "title": "x", "occurred_from": date(2026, 1, 1)},
    )
    with pytest.raises(ValidationError):
        await svc.update_delay_event_eot(
            db_session,
            delay_event_id=row.id,
            actor_id=None,
            eot_status="approved",
            eot_days_granted=None,
            eot_note=None,
        )


async def test_apply_notice_deadline_auto_judge_persists_when_apply(db_session) -> None:
    dispute = await _seed_dispute(db_session, dispute_type="claim")
    result = await svc.apply_notice_deadline_auto_judge(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        event_date=date(2026, 1, 1),
        override_days=None,
        apply=True,
    )
    assert result["applied"] is True
    await db_session.refresh(dispute)
    assert dispute.notice_deadline == date(2026, 1, 15)  # claim の既定 14 日


async def test_list_time_bar_alerts_excludes_closed_and_far_future(db_session) -> None:
    soon = await _seed_dispute(
        db_session,
        status="open",
        statute_limitations_date=date.today() + timedelta(days=5),
    )
    await _seed_dispute(
        db_session,
        status="closed",
        statute_limitations_date=date.today() + timedelta(days=1),
    )
    await _seed_dispute(
        db_session,
        status="open",
        statute_limitations_date=date.today() + timedelta(days=400),
    )
    alerts = await svc.list_time_bar_alerts(db_session)
    ids = [a["dispute_id"] for a in alerts]
    assert soon.id in ids
    assert len(ids) == 1


async def test_argument_positions_crud(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    row = await svc.add_argument_position(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "issue_no": 1,
            "issue_title": "遅延の帰責事由",
            "party": "ours",
            "stance": "claim",
            "content": "発注者の指示遅延が原因である。",
            "evidence_refs": [1, 2],
        },
    )
    assert row.party == "ours"
    rows = await svc.list_argument_positions(db_session, dispute_id=dispute.id)
    assert len(rows) == 1
    assert rows[0].evidence_refs == [1, 2]


async def test_settlement_options_compare_ranks_by_expected_value(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    low = await svc.add_settlement_option(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "option_no": 1,
            "title": "低額即時和解",
            "settlement_amount_jpy": 1_000_000,
            "probability_score": 90,
        },
    )
    high = await svc.add_settlement_option(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={
            "option_no": 2,
            "title": "高額訴訟",
            "settlement_amount_jpy": 5_000_000,
            "probability_score": 30,
        },
    )
    assert low.expected_value_jpy == 900_000
    assert high.expected_value_jpy == 1_500_000

    ranked = await svc.compare_settlement_options(db_session, dispute_id=dispute.id)
    assert ranked[0]["id"] == high.id
    assert ranked[0]["recommended"] is True
    assert ranked[1]["recommended"] is False

    updated = await svc.update_settlement_option(
        db_session,
        option_id=low.id,
        actor_id=None,
        data={"status": "accepted"},
    )
    assert updated.status == "accepted"


async def test_proceeding_stages_auto_completes_previous_active(db_session) -> None:
    dispute = await _seed_dispute(db_session)
    first = await svc.add_proceeding_stage(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={"stage": "negotiation", "started_at": date(2026, 1, 1)},
    )
    assert first.status == "active"

    second = await svc.add_proceeding_stage(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={"stage": "mediation", "started_at": date(2026, 2, 1)},
    )
    await db_session.refresh(first)
    assert first.status == "completed"
    assert first.ended_at == date(2026, 2, 1)
    assert second.status == "active"

    stages = await svc.list_proceeding_stages(db_session, dispute_id=dispute.id)
    assert [s.stage for s in stages] == ["negotiation", "mediation"]


async def test_proceeding_stages_retroactive_registration_keeps_ended_at_consistent(
    db_session,
) -> None:
    """新ステージの started_at が既存ステージの started_at より前でも
    ended_at < started_at という不整合レコードにならないこと（N7 回帰）."""
    dispute = await _seed_dispute(db_session)
    first = await svc.add_proceeding_stage(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={"stage": "negotiation", "started_at": date(2026, 2, 1)},
    )
    assert first.status == "active"

    # 遡及登録: 新ステージの開始日が既存アクティブステージの開始日より前
    second = await svc.add_proceeding_stage(
        db_session,
        dispute_id=dispute.id,
        actor_id=None,
        data={"stage": "mediation", "started_at": date(2026, 1, 1)},
    )
    await db_session.refresh(first)
    assert first.status == "completed"
    # ended_at は既存ステージ自身の started_at を下限にする（2026-01-01 ではなく 2026-02-01）
    assert first.ended_at == date(2026, 2, 1)
    assert first.ended_at >= first.started_at
    assert second.status == "active"


async def test_get_dispute_full_not_found(db_session) -> None:
    with pytest.raises(NotFoundError):
        await svc.get_dispute_full(db_session, dispute_id=999_999)
