"""Microsoft Sentinel 転送シンク（webhook）。

``SENTINEL_WEBHOOK_URL`` / ``SENTINEL_WEBHOOK_TOKEN`` 未設定時は無効
（何もしない）。設定時は fail-closed ではなく監査出力を止めない方針
（転送失敗は呼び出し元でログ・監視対象にする）。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def send_batch(
    payload: dict[str, Any],
    *,
    url: str | None = None,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """監査イベント要約を Sentinel の Log Ingestion エンドポイントへ転送する."""
    webhook_url = url or os.getenv("SENTINEL_WEBHOOK_URL")
    webhook_token = token or os.getenv("SENTINEL_WEBHOOK_TOKEN")
    if not webhook_url:
        return False
    headers = {"Content-Type": "application/json"}
    if webhook_token:
        headers["Authorization"] = f"Bearer {webhook_token}"
    owns_client = client is None
    async_client = client or httpx.AsyncClient(timeout=10.0)
    try:
        response = await async_client.post(
            webhook_url, json=payload, headers=headers
        )
        return 200 <= response.status_code < 300
    finally:
        if owns_client:
            await async_client.aclose()
