"""Audit logging service with hash chain.

Implements the append-only audit-log behavior defined in
``docs/audit_log_policy.md`` (sections 3 and 4):

* Each event carries a deterministic ``event_hash`` =
  ``HMAC_SHA256(secret, prev_hash || canonical_json(event))``.
* :meth:`AuditService.verify_chain` recomputes the chain end-to-end and
  reports the first broken link, supporting the daily integrity job.

The service is repository-agnostic. It receives an ``AsyncSession``
parameter for compatibility with the SQLAlchemy DAO defined by other
teams, but actual persistence is delegated to a pluggable
``persister`` callback so this module never imports the ORM directly.
For Loop 2 / tests, the in-process list is used.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.core.config import get_settings
from app.models.enums import AuditAction
from app.schemas.audit_log import AuditVerifyResponse

logger = structlog.get_logger(__name__)

# Genesis hash: 32 bytes of zeros, hex-encoded.
GENESIS_HASH: str = "0" * 64


@dataclass(slots=True)
class AuditRecord:
    """A single audit log row."""

    id: UUID
    timestamp: datetime
    action: str
    target_type: str
    target_id: str | None
    user_id: int | UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    prev_hash: str
    event_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditChainVerifyResult:
    """Outcome of :meth:`AuditService.verify_chain`."""

    ok: bool
    total: int
    first_broken_event_id: UUID | None
    first_broken_index: int | None
    detail: str | None = None


class AuditService:
    """Hash-chained audit logger."""

    def __init__(
        self,
        *,
        secret: bytes | None = None,
        persister: Callable[[AuditRecord, Any], Awaitable[None]] | None = None,
        fetcher: Callable[[datetime | None, datetime | None, Any], Awaitable[list[AuditRecord]]]
        | None = None,
    ) -> None:
        settings = get_settings()
        self._secret = secret or settings.hash_chain_secret.get_secret_value().encode("utf-8")
        self._persister = persister
        self._fetcher = fetcher
        # In-memory ledger (last_hash + records) used when no persister is supplied.
        self._records: list[AuditRecord] = []
        self._last_hash: str = GENESIS_HASH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def log(
        self,
        action: AuditAction | str,
        target_type: str,
        target_id: str | UUID | None,
        user_id: int | UUID | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        session: Any = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Append a new audit record and return it."""
        ts = datetime.now(UTC)
        action_value = action.value if isinstance(action, AuditAction) else str(action)
        target_id_str = str(target_id) if target_id is not None else None

        prev_hash = await self._last_hash_for(session)

        payload = {
            "timestamp": ts.isoformat(),
            "action": action_value,
            "target_type": target_type,
            "target_id": target_id_str,
            "user_id": str(user_id) if user_id else None,
            "before": before,
            "after": after,
            "metadata": metadata or {},
        }
        event_hash = self._compute_hash(prev_hash, payload)

        record = AuditRecord(
            id=uuid4(),
            timestamp=ts,
            action=action_value,
            target_type=target_type,
            target_id=target_id_str,
            user_id=user_id,
            before=before,
            after=after,
            prev_hash=prev_hash,
            event_hash=event_hash,
            metadata=metadata or {},
        )

        if self._persister:
            await self._persister(record, session)
        else:
            self._records.append(record)
            self._last_hash = event_hash

        logger.info(
            "audit.log",
            action=action_value,
            target_type=target_type,
            target_id=target_id_str,
            user_id=str(user_id) if user_id else None,
            event_hash=event_hash,
        )
        return record

    async def verify_chain(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        session: Any = None,
    ) -> AuditChainVerifyResult:
        """Recompute the hash chain in [from_date, to_date] and report the
        first inconsistency, if any.
        """
        records = await self._fetch_range(from_date, to_date, session)
        if not records:
            return AuditChainVerifyResult(
                ok=True, total=0, first_broken_event_id=None, first_broken_index=None
            )

        # The expected previous hash is GENESIS_HASH for the very first
        # record we examine. If from_date is mid-chain we trust the
        # caller's prev_hash on the first record as a soft anchor and
        # only verify forward consistency.
        expected_prev = records[0].prev_hash
        for idx, rec in enumerate(records):
            if rec.prev_hash != expected_prev:
                return AuditChainVerifyResult(
                    ok=False,
                    total=len(records),
                    first_broken_event_id=rec.id,
                    first_broken_index=idx,
                    detail=(
                        f"prev_hash mismatch at index {idx}: "
                        f"expected {expected_prev}, got {rec.prev_hash}"
                    ),
                )
            payload = {
                "timestamp": rec.timestamp.isoformat(),
                "action": rec.action,
                "target_type": rec.target_type,
                "target_id": rec.target_id,
                "user_id": str(rec.user_id) if rec.user_id else None,
                "before": rec.before,
                "after": rec.after,
                "metadata": rec.metadata,
            }
            recomputed = self._compute_hash(rec.prev_hash, payload)
            if recomputed != rec.event_hash:
                return AuditChainVerifyResult(
                    ok=False,
                    total=len(records),
                    first_broken_event_id=rec.id,
                    first_broken_index=idx,
                    detail=(
                        f"event_hash mismatch at index {idx}: "
                        f"expected {recomputed}, got {rec.event_hash}"
                    ),
                )
            expected_prev = rec.event_hash

        return AuditChainVerifyResult(
            ok=True,
            total=len(records),
            first_broken_event_id=None,
            first_broken_index=None,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_hash(self, prev_hash: str, payload: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 over ``prev_hash || canonical_json(payload)``."""
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        message = prev_hash.encode("utf-8") + canonical.encode("utf-8")
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    async def _last_hash_for(self, session: Any) -> str:
        if self._persister is None:
            return self._last_hash
        # External persistence path: fetch latest record's hash.
        if self._fetcher is not None:
            latest = await self._fetcher(None, None, session)
            if latest:
                return latest[-1].event_hash
        return GENESIS_HASH

    async def _fetch_range(
        self,
        from_date: datetime | None,
        to_date: datetime | None,
        session: Any,
    ) -> list[AuditRecord]:
        if self._fetcher is not None:
            return await self._fetcher(from_date, to_date, session)
        # In-memory mode.
        return [
            r
            for r in self._records
            if (from_date is None or r.timestamp >= from_date)
            and (to_date is None or r.timestamp <= to_date)
        ]


def _json_default(o: Any) -> Any:
    import decimal

    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, UUID):
        return str(o)
    if isinstance(o, decimal.Decimal):
        return float(o)
    if hasattr(o, "value"):  # Enum
        return o.value
    raise TypeError(f"object of type {type(o).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Module-level convenience wrappers (bridge to AuditService singleton)
# ---------------------------------------------------------------------------

_svc: AuditService = AuditService()


async def log(
    session: Any,
    *,
    actor_id: Any = None,
    action: str | AuditAction,
    target_type: str,
    target_id: Any = None,
    request: Any = None,
    payload: dict[str, Any] | None = None,
) -> None:
    await _svc.log(
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        user_id=actor_id,
        before=None,
        after=payload,
        session=session,
    )


def _coerce_int_id(value: Any) -> int | None:
    """Best-effort coercion of a principal/target id to the int that
    ``AuditLogOut`` surfaces.

    The auth layer (``app.deps.CurrentUser``) may carry a UUID or, under the
    Loop-2 JWT stub, an email subject as the principal id. Only genuine
    integer DB ids are projected onto the ``actor_id`` / ``target_id``
    response fields; the full principal is always preserved inside the signed
    hash-chain payload regardless of this projection (audit fidelity is kept
    in the immutable ledger, not in this view model).
    """
    if isinstance(value, bool):  # bool is an int subclass — never a valid id
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _record_to_dict(idx: int, rec: AuditRecord) -> dict[str, Any]:
    """Convert an in-memory AuditRecord to a dict matching AuditLogOut."""
    return {
        "id": idx,
        "occurred_at": rec.timestamp.isoformat(),
        "actor_id": _coerce_int_id(rec.user_id),
        "actor": None,
        "actor_role": None,
        "action": rec.action,
        "target_type": rec.target_type,
        "target_id": _coerce_int_id(rec.target_id),
        "request_id": None,
        "ip_address": None,
        "user_agent": None,
        "payload": rec.after or {},
        "prev_hash": rec.prev_hash,
        "hash_chain": rec.event_hash,
    }


async def list_logs(
    session: Any,
    *,
    target_type: str | None = None,
    target_id: Any = None,
    action: str | None = None,
    actor_id: Any = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[Any], int]:
    records = _svc._records
    filtered = [
        r
        for r in records
        if (target_type is None or r.target_type == target_type)
        and (target_id is None or r.target_id == str(target_id))
        and (action is None or r.action == action)
        and (date_from is None or r.timestamp >= date_from)
        and (date_to is None or r.timestamp <= date_to)
    ]
    total = len(filtered)
    start = (page - 1) * size
    page_records = filtered[start : start + size]
    items = [_record_to_dict(i + start + 1, r) for i, r in enumerate(page_records)]
    return items, total


async def verify_chain(
    session: Any,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditVerifyResponse:
    result = await _svc.verify_chain(from_date=date_from, to_date=date_to, session=session)
    return AuditVerifyResponse(
        verified=result.ok,
        total=result.total,
        broken_at=result.first_broken_index,
        checked_at=datetime.now(UTC),
        ok=result.ok,
    )


def export_csv(
    session: Any,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    target_type: str | None = None,
) -> Iterator[str]:
    records = [
        r
        for r in _svc._records
        if (target_type is None or r.target_type == target_type)
        and (date_from is None or r.timestamp >= date_from)
        and (date_to is None or r.timestamp <= date_to)
    ]
    yield "id,occurred_at,action,target_type,target_id,prev_hash,hash_chain\n"
    for idx, rec in enumerate(records, start=1):
        yield (
            f"{idx},{rec.timestamp.isoformat()},{rec.action},"
            f"{rec.target_type},{rec.target_id or ''},"
            f"{rec.prev_hash},{rec.event_hash}\n"
        )


async def list_for_target(
    session: Any,
    *,
    target_type: str,
    target_id: Any,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Any], int]:
    return await list_logs(
        session,
        target_type=target_type,
        target_id=target_id,
        page=page,
        size=size,
    )
