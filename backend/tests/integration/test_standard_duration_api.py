"""標準工期・短工期判定・価格転嫁シミュレータ API の統合テスト（#22/#25/#26）."""

from __future__ import annotations

from typing import Any

LW = "/api/v1/labor-wage"


async def test_standard_duration_crud_and_check(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#22: 登録 → 一覧 → 短工期判定."""
    r1 = await client.post(
        f"{LW}/standard-durations",
        json={
            "work_type": "とび・土工",
            "amount_min_jpy": 5_000_000,
            "amount_max_jpy": 20_000_000,
            "standard_days": 90,
            "effective_from": "2026-01-01",
            "source_ref": "標準工期（デモ）",
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["standard_days"] == 90

    r_list = await client.get(
        f"{LW}/standard-durations",
        params={"work_type": "とび・土工"},
        headers=auth_headers_admin,
    )
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    r_ok = await client.get(
        f"{LW}/short-duration-check",
        params={"work_type": "とび・土工", "amount_jpy": 10_000_000, "planned_days": 100},
        headers=auth_headers_admin,
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["status"] == "ok"

    r_short = await client.get(
        f"{LW}/short-duration-check",
        params={"work_type": "とび・土工", "amount_jpy": 10_000_000, "planned_days": 60},
        headers=auth_headers_admin,
    )
    assert r_short.status_code == 200
    body = r_short.json()
    assert body["status"] == "short"
    assert body["severity"] == "critical"  # 短縮率 33%

    r_missing = await client.get(
        f"{LW}/short-duration-check",
        params={"work_type": "解体", "amount_jpy": 10_000_000, "planned_days": 60},
        headers=auth_headers_admin,
    )
    assert r_missing.status_code == 404


async def test_price_simulator_endpoint(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """#25/#26: シミュレータ計算（決定論的）."""
    r = await client.post(
        f"{LW}/price-simulator",
        json={
            "contract_amount_jpy": 100_000_000,
            "labor_cost_jpy": 20_000_000,
            "material_cost_jpy": 30_000_000,
            "labor_change_rate": 0.08,
            "material_change_rate": 0.05,
            "pass_through_rate": 0.5,
        },
        headers=auth_headers_legal,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pass_through_amount_jpy"] == 1_550_000
    assert body["adjusted_amount_jpy"] == 101_550_000
    assert body["direction"] == "up"


async def test_price_simulator_validation(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """転嫁率 1.5 は 422."""
    r = await client.post(
        f"{LW}/price-simulator",
        json={
            "contract_amount_jpy": 100,
            "labor_cost_jpy": 0,
            "material_cost_jpy": 0,
            "labor_change_rate": 0.0,
            "material_change_rate": 0.0,
            "pass_through_rate": 1.5,
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 422
