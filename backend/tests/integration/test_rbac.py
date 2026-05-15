"""Role-based access control matrix (``docs/api_design.md`` §17).

Each row defines (role, method, path, expected_status). We loop over the
matrix and assert the API enforces it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="RBAC dependencies implemented in Loop 3")


# (role_fixture_name, method, path, expected_status_when_allowed_or_forbidden)
MATRIX = [
    # admin can do everything
    ("auth_headers_admin", "GET", "/api/v1/contracts", 200),
    ("auth_headers_admin", "GET", "/api/v1/users", 200),
    ("auth_headers_admin", "GET", "/api/v1/audit-logs", 200),
    # legal / reviewer can read contracts and audit, may not delete users
    ("auth_headers_legal", "GET", "/api/v1/contracts", 200),
    ("auth_headers_legal", "DELETE", "/api/v1/users/1", 403),
    # site / drafter can read own contracts, may not access audit logs
    ("auth_headers_site", "GET", "/api/v1/contracts", 200),
    ("auth_headers_site", "GET", "/api/v1/audit-logs", 403),
    ("auth_headers_site", "DELETE", "/api/v1/users/1", 403),
]


@pytest.mark.parametrize("role_fx, method, path, expected", MATRIX)
async def test_rbac_matrix(request, client, role_fx, method, path, expected):
    """Arrange: role headers. Act: call endpoint. Assert: expected status."""
    # Arrange
    headers = request.getfixturevalue(role_fx)
    # Act
    resp = await client.request(method, path, headers=headers)
    # Assert
    assert resp.status_code == expected, (
        f"{role_fx} {method} {path} -> {resp.status_code} (expected {expected})"
    )


async def test_unauthenticated_request_returns_401(client):
    """Arrange: no headers. Act: GET protected. Assert: 401."""
    # Arrange / Act
    resp = await client.get("/api/v1/contracts")
    # Assert
    assert resp.status_code == 401
