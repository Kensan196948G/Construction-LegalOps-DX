"""労務費基準 API の統合テスト（Issue #111）."""

from __future__ import annotations

from typing import Any

LW = "/api/v1/labor-wage"


async def test_standard_crud_latest_and_discrepancy(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """登録 → 一覧 → latest → 乖離率判定."""
    r1 = await client.post(
        f"{LW}/standards",
        json={
            "work_type": "とび・土工",
            "amount_jpy": 21_000,
            "prefecture": "東京都",
            "effective_from": "2026-04-01",
            "source_ref": "2026年4月基準",
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["amount_jpy"] == 21_000

    r2 = await client.post(
        f"{LW}/standards",
        json={"work_type": "とび・土工", "amount_jpy": 22_000, "effective_from": "2026-10-01"},
        headers=auth_headers_admin,
    )
    assert r2.status_code == 201

    r_list = await client.get(
        f"{LW}/standards?work_type=%E3%81%A8%E3%81%B3%E3%83%BB%E5%9C%9F%E5%B7%A5",
        headers=auth_headers_admin,
    )
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 2

    r_latest = await client.get(
        f"{LW}/standards/latest",
        params={"work_type": "とび・土工", "as_of": "2026-11-01"},
        headers=auth_headers_admin,
    )
    assert r_latest.status_code == 200
    assert r_latest.json()["amount_jpy"] == 22_000

    r_ok = await client.get(
        f"{LW}/discrepancy",
        params={"work_type": "とび・土工", "quote_day_jpy": 22_500},
        headers=auth_headers_admin,
    )
    assert r_ok.status_code == 200 and r_ok.json()["status"] == "ok"

    r_below = await client.get(
        f"{LW}/discrepancy",
        params={"work_type": "とび・土工", "quote_day_jpy": 19_000},
        headers=auth_headers_admin,
    )
    assert r_below.status_code == 200
    assert r_below.json()["status"] == "below"
    assert r_below.json()["shortage_rate"] > 0


async def test_latest_missing_returns_404(client: Any, auth_headers_legal: dict[str, str]) -> None:
    """基準未登録の工種は 404."""
    r = await client.get(
        f"{LW}/standards/latest", params={"work_type": "解体"}, headers=auth_headers_legal
    )
    assert r.status_code == 404
