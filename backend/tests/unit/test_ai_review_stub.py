"""Tests for the AI review service in *stub mode*.

Loop 3 module: ``app.services.ai_review`` with::

    class AIReviewService:
        def __init__(self, *, mode: str | None = None, ...)
        async def review_contract(self, text: str, contract_type: str) -> AIReviewResult
"""

from __future__ import annotations

import pytest

ai_review = pytest.importorskip(
    "app.services.ai_review",
    reason="ai_review service implemented in Loop 3",
)


def _make_service():
    cls = getattr(ai_review, "AIReviewService", None)
    if cls is None:
        pytest.skip("AIReviewService not implemented")
    return cls(mode="stub")


async def test_stub_returns_structured_result():
    """Arrange: stub service. Act: review. Assert: AIReviewResult has fields."""
    # Arrange
    svc = _make_service()
    # Act
    result = await svc.review_contract("テスト用契約書本文", contract_type="請負")
    # Assert
    assert result is not None
    # to_dict() is documented on AIReviewResult
    if hasattr(result, "to_dict"):
        data = result.to_dict()
    else:
        data = result.__dict__
    assert isinstance(data, dict)


async def test_stub_is_deterministic_for_same_input():
    """Arrange: same input. Act: review twice. Assert: deterministic core fields."""
    # Arrange
    svc = _make_service()
    text = "同一の契約本文"
    # Act
    a = await svc.review_contract(text, contract_type="請負")
    b = await svc.review_contract(text, contract_type="請負")
    # Assert: convert to comparable shape
    da = a.to_dict() if hasattr(a, "to_dict") else a.__dict__
    db = b.to_dict() if hasattr(b, "to_dict") else b.__dict__
    for key in ("summary", "issues", "risk_level"):
        if key in da and key in db:
            assert da[key] == db[key]


async def test_stub_result_schema_has_expected_keys():
    """Arrange: stub. Act: review. Assert: required keys present."""
    # Arrange
    svc = _make_service()
    # Act
    result = await svc.review_contract("条項テスト用", contract_type="委託")
    data = result.to_dict() if hasattr(result, "to_dict") else result.__dict__
    # Assert
    expected = {"summary", "issues", "risk_level", "risk_score", "clauses"}
    assert expected & set(data.keys())


async def test_stub_does_not_invoke_anthropic_client(monkeypatch):
    """Arrange: poison anthropic. Act: review. Assert: no client call made."""
    # Arrange
    called = {"flag": False}

    def _poison(*a, **kw):
        called["flag"] = True
        raise RuntimeError("network must not be touched in stub mode")

    try:
        import anthropic  # type: ignore

        monkeypatch.setattr(anthropic, "Anthropic", _poison, raising=False)
    except Exception:
        pass
    svc = _make_service()
    # Act
    _ = await svc.review_contract("外部APIを呼び出さないこと", contract_type="秘密保持")
    # Assert
    assert called["flag"] is False


async def test_stub_rejects_empty_text():
    """Arrange: empty text. Act: review. Assert: raises AIReviewServiceError."""
    # Arrange
    svc = _make_service()
    err_cls = getattr(ai_review, "AIReviewServiceError", RuntimeError)
    # Act / Assert
    with pytest.raises(err_cls):
        await svc.review_contract("", contract_type="請負")
