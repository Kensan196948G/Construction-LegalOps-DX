"""JPO 特許情報取得 API クライアントのユニットテスト."""

from __future__ import annotations

import zipfile
from io import BytesIO

import httpx
import pytest

from app.services.jpo_client import (
    JpoApiClient,
    JpoApiError,
    JpoRateLimitError,
    extract_zip_text,
)


def test_demo_mode_default_without_credentials():
    client = JpoApiClient(mode="demo")
    assert client.is_demo is True
    assert client.mode_label == "demo"


def test_live_mode_requires_credentials():
    client = JpoApiClient(mode="live", api_id="", api_password="")
    assert client.is_demo is True  # ID/PW 未設定ならデモ扱い（fail-closed ではないが安全側）
    client2 = JpoApiClient(mode="live", api_id="user01", api_password="pass")
    assert client2.is_demo is False
    assert client2.mode_label == "live"


def test_demo_call_app_progress():
    import asyncio

    client = JpoApiClient(mode="demo")
    result = asyncio.run(client.call(domain="patent", api="app_progress", case_number="2026000001"))
    assert result.status_code == "100"
    assert result.data["applicationNumber"] == "2026000001"
    assert result.data["inventionTitle"]
    assert result.data["progress"]


def test_demo_call_registration_and_reference():
    import asyncio

    client = JpoApiClient(mode="demo")
    reg = asyncio.run(
        client.call(domain="patent", api="registration_info", case_number="2026000001")
    )
    assert reg.data["registrationNumber"] == "7000001"
    ref = asyncio.run(
        client.call(domain="patent", api="case_number_reference", case_number="2026000001")
    )
    assert ref.data["publicationNumber"]


def test_demo_call_applicant_attorney():
    import asyncio

    client = JpoApiClient(mode="demo")
    result = asyncio.run(
        client.call(domain="patent", api="applicant_attorney", case_number="みらい建設工業")
    )
    rows = result.data["applicantAttorney"]
    assert rows[0]["name"] == "みらい建設工業(株)"
    assert rows[0]["applicantAttorneyCd"] == "000000001"


def test_demo_zip_contains_xml():
    import asyncio

    client = JpoApiClient(mode="demo")
    data = asyncio.run(
        client.download_doc_zip(
            domain="patent", api="app_doc_cont_refusal_reason", case_number="2026000003"
        )
    )
    assert data.startswith(b"PK")
    parts = extract_zip_text(data)
    assert parts
    assert "拒絶理由通知書" in parts[0]["text"]


def test_extract_zip_text_plain_bytes():
    text = "書類（デモ）\n本文"
    parts = extract_zip_text(text.encode("utf-8"))
    assert parts
    assert "本文" in parts[0]["text"]


def test_extract_zip_text_shift_jis():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.xml", "拒絶理由通知書".encode("cp932"))
    parts = extract_zip_text(buf.getvalue())
    assert "拒絶理由通知書" in parts[0]["text"]


def test_live_call_error_status_code_raises():
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "tok-1",
                    "refresh_token": "ref-1",
                    "expires_in": 3600,
                    "refresh_expires_in": 28800,
                },
            )
        return httpx.Response(
            200,
            json={"result": {"statusCode": "420", "errorMessage": "アクセス上限超過"}},
        )

    client = JpoApiClient(
        mode="live",
        api_id="user01",
        api_password="pass",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(JpoRateLimitError):
        asyncio.run(client.call(domain="patent", api="app_progress", case_number="2026000001"))


def test_live_call_http_429_raises():
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "tok-1",
                    "refresh_token": "ref-1",
                    "expires_in": 3600,
                    "refresh_expires_in": 28800,
                },
            )
        return httpx.Response(429, json={"result": {"statusCode": "429"}})

    client = JpoApiClient(
        mode="live",
        api_id="user01",
        api_password="pass",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(JpoRateLimitError):
        asyncio.run(client.call(domain="patent", api="app_progress", case_number="2026000001"))


def test_live_call_success_parses_result():
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "tok-1",
                    "refresh_token": "ref-1",
                    "expires_in": 3600,
                    "refresh_expires_in": 28800,
                },
            )
        return httpx.Response(
            200,
            json={
                "result": {
                    "statusCode": "100",
                    "errorMessage": "",
                    "remainAccessCount": "399",
                    "data": {"applicationNumber": "2026000001", "inventionTitle": "テスト"},
                }
            },
        )

    client = JpoApiClient(
        mode="live",
        api_id="user01",
        api_password="pass",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(client.call(domain="patent", api="app_progress", case_number="2026000001"))
    assert result.remaining == 399
    assert result.data["inventionTitle"] == "テスト"


def test_live_token_acquisition():
    """トークン取得 → API 呼び出しの順序を検証する。"""
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "tok-1",
                    "refresh_token": "ref-1",
                    "expires_in": 3600,
                    "refresh_expires_in": 28800,
                },
            )
        auth = request.headers.get("Authorization", "")
        assert auth == "Bearer tok-1", f"unexpected auth header: {auth}"
        return httpx.Response(
            200,
            json={
                "result": {
                    "statusCode": "100",
                    "data": {"applicationNumber": "2026000001"},
                }
            },
        )

    client = JpoApiClient(
        mode="live",
        api_id="user01",
        api_password="pass",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(client.call(domain="patent", api="app_progress", case_number="2026000001"))
    assert result.data["applicationNumber"] == "2026000001"


def test_rate_limit_wait_is_noop_in_demo():
    client = JpoApiClient(mode="demo", max_calls_per_minute=2)
    import asyncio

    async def run() -> None:
        for _ in range(5):
            await client._rate_limit_wait()

    asyncio.run(run())
    # デモでは待機しないため即時完了する（ここに到達すれば OK）


def test_jpo_api_error_type():
    assert issubclass(JpoRateLimitError, JpoApiError)
