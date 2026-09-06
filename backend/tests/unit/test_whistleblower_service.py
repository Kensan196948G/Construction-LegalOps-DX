"""内部通報・調査管理サービスの単体テスト（Issue #123）.

最重要: 通報者情報隔離（``get_reporter_profile``）を admin/investigator/
非関係者の 3 パターンで検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import whistleblower_service as wb


async def _make_user(db_session, *, role: str, name: str = "user") -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="部署")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.example",
        display_name=name,
        role=role,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return int(user.id)


async def test_create_report_numbering_and_timeline(db_session) -> None:
    """#125: 採番（WB-YYYY-NNNNNN）・受付タイムライン記録."""
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="harassment",
        title="上司からのハラスメント",
        description="詳細内容",
        reporter_name="山田太郎",
        contact_email="yamada@example.com",
    )
    assert report.report_no.startswith("WB-")
    assert report.status == "received"
    assert report.created_by == reporter_id

    timeline = await wb.list_timeline(db_session, report_id=report.id, role="admin", user_id=None)
    assert any(e.event_type == "received" for e in timeline)


async def test_anonymous_report_stores_no_identity(db_session) -> None:
    """#126: 匿名通報は created_by / reporter_profile のいずれにも識別情報を残さない."""
    reporter_id = await _make_user(db_session, role="drafter", name="匿名通報者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="corruption",
        title="談合の疑い",
        description="詳細",
        is_anonymous=True,
    )
    assert report.is_anonymous is True
    assert report.created_by is None
    assert report.updated_by is None

    profile = await wb.get_reporter_profile(
        db_session, role="admin", user_id=None, report_id=report.id
    )
    assert profile is None


async def test_anonymous_report_rejects_identity_fields(db_session) -> None:
    """#126: 匿名通報で識別情報を渡すと拒否される（fail-closed）."""
    with pytest.raises(ValidationError):
        await wb.create_report(
            db_session,
            actor_id=None,
            category="other",
            title="t",
            description="d",
            is_anonymous=True,
            reporter_name="漏洩してはいけない名前",
        )


async def test_reporter_identity_isolated_from_non_investigators(db_session) -> None:
    """最重要: 通報者情報は調査担当者 ACL 保有者・admin/auditor のみ閲覧可.

    - admin: 閲覧可
    - ACL 付与された investigator: 閲覧可
    - ACL 無しの一般ロール（drafter）: 403（隔離される）
    """
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    investigator_id = await _make_user(db_session, role="reviewer", name="調査担当者")
    outsider_id = await _make_user(db_session, role="drafter", name="無関係者")

    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="labor",
        title="残業代未払い",
        description="詳細",
        reporter_name="通報 太郎",
        contact_email="tsuho@example.com",
    )

    # admin は無条件で閲覧可
    admin_view = await wb.get_reporter_profile(
        db_session, role="admin", user_id=None, report_id=report.id
    )
    assert admin_view is not None
    assert admin_view.reporter_name == "通報 太郎"

    # ACL 無しの一般ロールは 403
    with pytest.raises(ForbiddenError):
        await wb.get_reporter_profile(
            db_session, role="drafter", user_id=outsider_id, report_id=report.id
        )

    # 案件本体（get_report）も同様に ACL 必須
    with pytest.raises(ForbiddenError):
        await wb.get_report(db_session, role="drafter", user_id=outsider_id, report_id=report.id)

    # 調査担当者 ACL を付与すると閲覧可能になる
    await wb.grant_case_access(
        db_session,
        report_id=report.id,
        actor_id=None,
        user_id=investigator_id,
        role_in_case="investigator",
        can_view_reporter_identity=True,
    )
    investigator_view = await wb.get_reporter_profile(
        db_session, role="reviewer", user_id=investigator_id, report_id=report.id
    )
    assert investigator_view is not None
    assert investigator_view.contact_email == "tsuho@example.com"

    # 案件本体も ACL 保有者は閲覧可
    seen = await wb.get_report(
        db_session, role="reviewer", user_id=investigator_id, report_id=report.id
    )
    assert seen.id == report.id

    # 依然として無関係者は隔離されたまま
    with pytest.raises(ForbiddenError):
        await wb.get_reporter_profile(
            db_session, role="drafter", user_id=outsider_id, report_id=report.id
        )


async def test_case_access_without_identity_flag_hides_reporter(db_session) -> None:
    """observer など identity フラグ無し付与では reporter profile は見えない."""
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    observer_id = await _make_user(db_session, role="reviewer", name="陪席者")

    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="safety",
        title="安全管理の不備",
        description="詳細",
        reporter_name="秘匿太郎",
    )
    await wb.grant_case_access(
        db_session,
        report_id=report.id,
        actor_id=None,
        user_id=observer_id,
        role_in_case="observer",
        can_view_reporter_identity=False,
    )
    # 案件本体は見えるが reporter profile は見えない
    seen = await wb.get_report(
        db_session, role="reviewer", user_id=observer_id, report_id=report.id
    )
    assert seen.id == report.id
    with pytest.raises(ForbiddenError):
        await wb.get_reporter_profile(
            db_session, role="reviewer", user_id=observer_id, report_id=report.id
        )


async def test_revoke_case_access_removes_visibility(db_session) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    investigator_id = await _make_user(db_session, role="reviewer", name="調査担当者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="fraud",
        title="経費不正",
        description="詳細",
    )
    grant = await wb.grant_case_access(
        db_session,
        report_id=report.id,
        actor_id=None,
        user_id=investigator_id,
        role_in_case="investigator",
    )
    assert await wb.has_case_access(
        db_session, role="reviewer", user_id=investigator_id, report_id=report.id
    )
    ok = await wb.revoke_case_access(
        db_session, report_id=report.id, actor_id=None, grant_id=grant.id
    )
    assert ok is True
    assert not await wb.has_case_access(
        db_session, role="reviewer", user_id=investigator_id, report_id=report.id
    )


async def test_promote_to_matter_links_investigative_matter(db_session) -> None:
    """#128: Investigative Matter 連携（法務 Matter との紐付け）."""
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    admin_id = await _make_user(db_session, role="admin", name="管理者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="compliance",
        title="下請法違反の疑い",
        description="詳細",
        severity="high",
    )
    updated = await wb.promote_to_matter(
        db_session, report_id=report.id, role="admin", user_id=admin_id
    )
    assert updated.matter_id is not None

    with pytest.raises(ConflictError):
        await wb.promote_to_matter(db_session, report_id=report.id, role="admin", user_id=admin_id)


async def test_status_transition_and_terminal_lock(db_session) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="other",
        title="その他事案",
        description="詳細",
    )
    updated = await wb.set_status(
        db_session, report_id=report.id, role="admin", user_id=None, status="investigating"
    )
    assert updated.status == "investigating"
    closed = await wb.set_status(
        db_session,
        report_id=report.id,
        role="admin",
        user_id=None,
        status="closed",
        note="是正済み",
    )
    assert closed.closed_at is not None
    with pytest.raises(ConflictError):
        await wb.set_status(
            db_session, report_id=report.id, role="admin", user_id=None, status="investigating"
        )


async def test_evidence_interview_action_lifecycle(db_session) -> None:
    """#129/#130/#132/#133: 証拠・ヒアリング・是正措置/再発防止の一連の流れ."""
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    investigator_id = await _make_user(db_session, role="reviewer", name="調査担当者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="harassment",
        title="ハラスメント調査",
        description="詳細",
    )
    await wb.grant_case_access(
        db_session,
        report_id=report.id,
        actor_id=None,
        user_id=investigator_id,
        role_in_case="investigator",
    )

    evidence = await wb.add_evidence(
        db_session,
        report_id=report.id,
        role="reviewer",
        user_id=investigator_id,
        evidence_type="email",
        description="メール証跡",
        preserved=True,
    )
    assert evidence.preserved is True

    interview = await wb.add_interview(
        db_session,
        report_id=report.id,
        role="reviewer",
        user_id=investigator_id,
        interviewee_type="witness",
        conducted_at=datetime.now(UTC),
        summary="目撃証言",
    )
    assert interview.interviewee_type == "witness"

    action = await wb.add_action(
        db_session,
        report_id=report.id,
        role="reviewer",
        user_id=investigator_id,
        action_category="corrective",
        title="加害者への懲戒処分",
    )
    assert action.status == "open"
    updated_action = await wb.update_action_status(
        db_session,
        report_id=report.id,
        action_id=action.id,
        role="reviewer",
        user_id=investigator_id,
        status="completed",
    )
    assert updated_action.completed_at is not None

    prevention = await wb.add_action(
        db_session,
        report_id=report.id,
        role="reviewer",
        user_id=investigator_id,
        action_category="preventive",
        title="ハラスメント研修の実施",
    )
    assert prevention.action_category == "preventive"

    evidences = await wb.list_evidence(
        db_session, report_id=report.id, role="reviewer", user_id=investigator_id
    )
    assert len(evidences) == 1
    interviews = await wb.list_interviews(
        db_session, report_id=report.id, role="reviewer", user_id=investigator_id
    )
    assert len(interviews) == 1
    actions = await wb.list_actions(
        db_session, report_id=report.id, role="reviewer", user_id=investigator_id
    )
    assert len(actions) == 2


async def test_evidence_forbidden_without_case_access(db_session) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    outsider_id = await _make_user(db_session, role="drafter", name="無関係者")
    report = await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="other",
        title="事案",
        description="詳細",
    )
    with pytest.raises(ForbiddenError):
        await wb.add_evidence(
            db_session,
            report_id=report.id,
            role="drafter",
            user_id=outsider_id,
            evidence_type="document",
        )


async def test_aggregate_report_has_no_identifying_fields(db_session) -> None:
    """#134/#135: 経営報告匿名集計は個人特定情報を一切含まない."""
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    await wb.create_report(
        db_session,
        actor_id=reporter_id,
        category="harassment",
        title="ハラスメント事案A",
        description="詳細",
        reporter_name="非公開太郎",
    )
    await wb.create_report(
        db_session,
        actor_id=None,
        category="fraud",
        title="不正会計事案",
        description="詳細",
        is_anonymous=True,
    )
    result = await wb.aggregate_report(db_session)
    assert result["total"] >= 2
    assert result["anonymous_count"] >= 1
    assert "harassment" in result["by_category"]
    serialized = str(result)
    assert "非公開太郎" not in serialized
    assert "ハラスメント事案A" not in serialized
    assert "不正会計事案" not in serialized


async def test_get_report_not_found(db_session) -> None:
    with pytest.raises(NotFoundError):
        await wb.get_report(db_session, role="admin", user_id=None, report_id=999_999)
