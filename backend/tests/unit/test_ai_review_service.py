"""Unit tests for ``app.services.ai_review_service``.

Covers:
  - ``start_review()`` in stub mode (AI_REVIEW_STUB=1)
  - ``_to_dict()`` helper via start_review output
  - contract not found → LookupError
  - non-stub mode → HTTPException 501

Target coverage: >= 80 % of ai_review_service.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_review_service import start_review

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(contract: object | None = MagicMock()) -> AsyncMock:
    """Return a session mock whose ``session.get`` returns *contract*."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=contract)
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    return session


def _make_contract(contract_id: int = 1) -> MagicMock:
    c = MagicMock()
    c.id = contract_id
    return c


def _make_payload(
    *,
    review_type: str = "ai",
    ai_model: str | None = None,
) -> MagicMock:
    p = MagicMock()
    p.review_type = review_type
    p.ai_model = ai_model
    return p


# ---------------------------------------------------------------------------
# 1. Stub mode: AI_REVIEW_STUB=1 — basic happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_mode_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Arrange: stub mode + valid contract. Act: start_review. Assert: dict returned."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract(1))
    payload = _make_payload()

    # Act
    result = await start_review(
        session,
        contract_id=1,
        user_id=99,
        payload=payload,
    )

    # Assert
    assert isinstance(result, dict)
    assert result["contract_id"] == 1


# ---------------------------------------------------------------------------
# 2. Stub mode: result has expected keys (_to_dict coverage — lines 61-83)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_result_has_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: stub mode. Act: start_review. Assert: all _to_dict keys present."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())
    payload = _make_payload()

    # Act
    result = await start_review(
        session,
        contract_id=1,
        user_id=1,
        payload=payload,
    )

    # Assert — keys defined in _to_dict
    expected_keys = {
        "id",
        "contract_id",
        "review_type",
        "status",
        "ai_model",
        "overall_risk",
        "risk_score",
        "summary",
        "started_at",
        "finished_at",
        "reviewer_id",
        "ai_input_tokens",
        "ai_output_tokens",
        "result",
        "findings",
        "suggested_actions",
        "disclaimer",
        "created_at",
        "updated_at",
    }
    assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# 3. Stub mode: status is RUNNING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_status_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: stub mode. Act: start_review. Assert: status == 'running'."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())
    payload = _make_payload()

    # Act
    result = await start_review(session, contract_id=1, user_id=1, payload=payload)

    # Assert
    from app.models.enums import ReviewStatus

    assert result["status"] == ReviewStatus.RUNNING.value


# ---------------------------------------------------------------------------
# 4. Stub mode: ai_model defaults to "stub" when payload has no ai_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_default_ai_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: payload.ai_model=None. Act: start_review. Assert: ai_model=='stub'."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())
    payload = _make_payload(ai_model=None)

    # Act
    result = await start_review(session, contract_id=1, user_id=1, payload=payload)

    # Assert
    assert result["ai_model"] == "stub"


# ---------------------------------------------------------------------------
# 5. Stub mode: custom ai_model is preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_custom_ai_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: payload.ai_model='claude-3'. Act: start_review. Assert: preserved."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())
    payload = _make_payload(ai_model="claude-3")

    # Act
    result = await start_review(session, contract_id=1, user_id=1, payload=payload)

    # Assert
    assert result["ai_model"] == "claude-3"


# ---------------------------------------------------------------------------
# 6. Stub mode: disclaimer is non-empty Japanese text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_disclaimer_is_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: stub mode. Act: start_review. Assert: disclaimer is nonempty."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())

    # Act
    result = await start_review(session, contract_id=1, user_id=1, payload=_make_payload())

    # Assert
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


# ---------------------------------------------------------------------------
# 7. Stub mode: findings and suggested_actions are lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_findings_are_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: stub mode, result={}.  Act: start_review. Assert: findings=[]."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())

    # Act
    result = await start_review(session, contract_id=1, user_id=1, payload=_make_payload())

    # Assert
    assert isinstance(result["findings"], list)
    assert isinstance(result["suggested_actions"], list)


# ---------------------------------------------------------------------------
# 8. Contract not found → LookupError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_contract_not_found_raises_lookup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: session.get returns None. Act: start_review. Assert: LookupError."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(contract=None)  # contract not found

    # Act / Assert
    with pytest.raises(LookupError, match="contract 999 not found"):
        await start_review(session, contract_id=999, user_id=1, payload=_make_payload())


# ---------------------------------------------------------------------------
# 9. Non-stub mode (AI_REVIEW_STUB unset) → HTTPException 501
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_non_stub_raises_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: AI_REVIEW_STUB not set. Act: start_review. Assert: HTTP 501."""
    from fastapi import HTTPException

    # Arrange — ensure env var is absent
    monkeypatch.delenv("AI_REVIEW_STUB", raising=False)
    session = _make_session(_make_contract())

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        await start_review(session, contract_id=1, user_id=1, payload=_make_payload())

    assert exc_info.value.status_code == 501


# ---------------------------------------------------------------------------
# 10. Idempotency key parameter accepted without error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_review_stub_accepts_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arrange: idempotency_key provided. Act: start_review. Assert: no error."""
    # Arrange
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    session = _make_session(_make_contract())

    # Act
    result = await start_review(
        session,
        contract_id=1,
        user_id=1,
        payload=_make_payload(),
        idempotency_key="idem-key-abc123",
    )

    # Assert
    assert isinstance(result, dict)
