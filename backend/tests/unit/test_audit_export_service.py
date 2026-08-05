"""監査ログ WORM 出力サービスのテスト."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models.audit_log import AuditLog
from app.services import audit_export_service


def _seed_audit_rows(db_session, *, count: int = 3) -> list[AuditLog]:
    rows: list[AuditLog] = []
    prev: str | None = None
    base = datetime.now(UTC) - timedelta(days=1)
    for i in range(count):
        payload = {"after": {"i": i}}
        canonical = audit_export_service._canonical_json(payload)
        chain = AuditLog.compute_hash(prev, canonical)
        row = AuditLog(
            occurred_at=base + timedelta(minutes=i),
            actor_id=1,
            actor_role="admin",
            action=f"test.action.{i}",
            target_type="contracts",
            target_id=i + 1,
            payload=payload,
            previous_hash=prev,
            hash_chain=chain,
        )
        db_session.add(row)
        prev = chain
        rows.append(row)
    return rows


async def test_export_audit_batch_writes_jsonl_and_job(
    db_session, tmp_path: Path
) -> None:
    _seed_audit_rows(db_session, count=3)
    since = datetime.now(UTC) - timedelta(days=2)
    until = datetime.now(UTC) + timedelta(days=1)

    result = await audit_export_service.export_audit_batch(
        db_session,
        since=since,
        until=until,
        export_dir=str(tmp_path),
        actor_id=1,
    )

    # 共有 PG テスト DB には他テストの監査行も含まれるため、>= で検証する
    assert result["record_count"] >= 3
    assert result["status"] == "completed"
    assert Path(result["file_path"]).exists()

    lines = Path(result["file_path"]).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == result["record_count"] + 1  # 行 + メタ行
    assert result["merkle_root"] in lines[-1]
    assert lines[-1].startswith("{")

    jobs = await audit_export_service.list_export_jobs(db_session)
    assert len(jobs) == 1
    assert jobs[0].job_no == result["job_no"]


async def test_export_empty_range(db_session, tmp_path: Path) -> None:
    _seed_audit_rows(db_session, count=2)
    since = datetime.now(UTC) + timedelta(days=10)
    until = datetime.now(UTC) + timedelta(days=11)
    result = await audit_export_service.export_audit_batch(
        db_session,
        since=since,
        until=until,
        export_dir=str(tmp_path),
    )
    assert result["record_count"] == 0
    lines = Path(result["file_path"]).read_text(encoding="utf-8").strip().splitlines()
    assert lines[-1].startswith("{")
