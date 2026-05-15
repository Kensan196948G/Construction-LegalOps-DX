"""Unit tests for the audit-log hash chain.

The hash chain primitive lives in ``app.core.security``:

* ``compute_hash_chain(prev_hash, payload) -> str``
* ``verify_hash_chain(prev_hash, payload, expected_hash) -> bool``

Spec: ``docs/audit_log_policy.md`` and ``docs/security_policy.md``.
"""

from __future__ import annotations

import pytest

security = pytest.importorskip("app.core.security")


def test_hash_chain_deterministic_for_same_input():
    """Arrange: same payload twice. Act: hash. Assert: identical."""
    # Arrange
    prev = "0" * 64
    payload = {"action": "contract.create", "id": 1}
    # Act
    h1 = security.compute_hash_chain(prev, payload)
    h2 = security.compute_hash_chain(prev, payload)
    # Assert
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_hash_chain_links_change_with_prev_hash():
    """Arrange: same payload, different prev. Act: hash. Assert: differ."""
    # Arrange
    payload = {"action": "contract.update", "id": 1}
    # Act
    h1 = security.compute_hash_chain("0" * 64, payload)
    h2 = security.compute_hash_chain("a" * 64, payload)
    # Assert
    assert h1 != h2


def test_hash_chain_links_change_with_payload():
    """Arrange: same prev, different payload. Act: hash. Assert: differ."""
    # Arrange
    prev = "0" * 64
    # Act
    h1 = security.compute_hash_chain(prev, {"a": 1})
    h2 = security.compute_hash_chain(prev, {"a": 2})
    # Assert
    assert h1 != h2


def test_verify_hash_chain_detects_tamper():
    """Arrange: build chain, then mutate payload. Act: verify. Assert: False."""
    # Arrange
    prev = "0" * 64
    payload = {"action": "contract.delete", "id": 42}
    h = security.compute_hash_chain(prev, payload)
    # Act
    tampered = dict(payload, id=99)
    ok = security.verify_hash_chain(prev, tampered, h)
    # Assert
    assert ok is False
    assert security.verify_hash_chain(prev, payload, h) is True


def test_hash_chain_genesis_prev_accepts_none_and_zero_hash():
    """Arrange: genesis row. Act: hash with None vs zeros. Assert: identical."""
    # Arrange
    payload = {"genesis": True}
    # Act
    h_none = security.compute_hash_chain(None, payload)
    h_zero = security.compute_hash_chain("0" * 64, payload)
    # Assert
    assert h_none == h_zero


def test_hash_chain_rejects_invalid_prev_hash():
    """Arrange: bogus prev_hash. Act: compute. Assert: ValueError."""
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        security.compute_hash_chain("not-hex", {"x": 1})


def test_hash_chain_sequence_is_continuous():
    """Arrange: chain of 5 entries. Act: roll forward. Assert: each verifies."""
    # Arrange
    entries = [{"i": i} for i in range(5)]
    prev = "0" * 64
    hashes: list[str] = []
    # Act
    for e in entries:
        h = security.compute_hash_chain(prev, e)
        hashes.append(h)
        prev = h
    # Assert: replay and verify each link
    prev = "0" * 64
    for entry, h in zip(entries, hashes):
        assert security.verify_hash_chain(prev, entry, h)
        prev = h
