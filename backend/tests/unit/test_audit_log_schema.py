"""Regression tests for audit-log schema serialization.

PostgreSQL stores ``audit_logs.ip_address`` as INET and asyncpg returns
``ipaddress`` objects; SQLite returns plain strings. The schema must accept
both (the mismatch previously 500'd ``GET /audit-logs`` only on the
production-parity stack — CI run 29691289815).
"""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address

from app.schemas.audit_log import AuditLogOut


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": 1,
        "occurred_at": datetime.now(UTC),
        "action": "contract.create",
        "target_type": "contracts",
        "hash_chain": "0" * 64,
    }
    data.update(overrides)
    return data


def test_ip_address_coerced_from_pg_inet_ipv4() -> None:
    out = AuditLogOut.model_validate(_payload(ip_address=IPv4Address("127.0.0.1")))
    assert out.ip_address == "127.0.0.1"


def test_ip_address_coerced_from_pg_inet_ipv6() -> None:
    out = AuditLogOut.model_validate(_payload(ip_address=IPv6Address("::1")))
    assert out.ip_address == "::1"


def test_ip_address_accepts_plain_string() -> None:
    out = AuditLogOut.model_validate(_payload(ip_address="10.0.0.8"))
    assert out.ip_address == "10.0.0.8"


def test_ip_address_accepts_none() -> None:
    out = AuditLogOut.model_validate(_payload(ip_address=None))
    assert out.ip_address is None
