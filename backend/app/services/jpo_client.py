"""JPO 特許情報取得 API クライアント.

特許庁（JPO）の「特許情報取得 API」（https://ip-data.jpo.go.jp）にアクセスする。
知財管理・競合出願ウォッチ・審査書類収集の 3 機能すべてがこのクライアントを使う。

仕様（特許情報取得 API 利用の手引き / アクセス方法）:
- 認証: ``POST {base}/auth/token`` に ``grant_type=password`` で ID/PW を送り、
  ``access_token``（有効 1 時間）と ``refresh_token``（有効 8 時間）を取得する。
  失効後は ``grant_type=refresh_token`` で再取得できる。
- API: ``GET {base}/api/{domain}/v1/{api}/{案件番号}`` に
  ``Authorization: Bearer <access_token>`` を付与する。
- レスポンス: ``{"result": {"statusCode": "100", "errorMessage": "", ...}}``。
  ``statusCode=100`` が成功。書類系は ``application/zip`` が返る。
- アクセス制限: 国内 API は 1 分間に 10 回以下、API ごとに日次上限あり。
  本クライアントは固定ウィンドウのレートリミッタで 1 分間の呼び出しを調整する。

デモモード:
- ``settings.jpo_api_mode == "demo"``（MVP 既定）の場合は外部 API を呼ばず、
  決定的なデモデータを返す。ID/PW 未設定でも全機能が動作する。
- デモデータは実在の出願番号・企業名を避け、架空の値のみを使用する。
"""

from __future__ import annotations

import asyncio
import io
import time
import zipfile
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

import httpx

from app.core.config import settings

JpoDomain = Literal["patent", "design", "trademark"]
IpType = Literal["patent", "design", "trademark"]

# 国内 API のエンドポイント定義（OpenAPI 仕様 2026-03-02 版より）。
# キー: (domain, 種別) → パス。案件番号は末尾のパスパラメータ。
_DOMAIN_PREFIX = {
    "patent": "api/patent/v1",
    "design": "api/design/v1",
    "trademark": "api/trademark/v1",
}


class JpoApiError(Exception):
    """JPO API 呼び出しの失敗（認証・上限到達・HTTP エラー等）。"""


class JpoRateLimitError(JpoApiError):
    """日次アクセス上限に到達した。"""


@dataclass
class JpoResult:
    """JPO API の共通レスポンスラッパー（statusCode=100 の成功時のみ生成）。"""

    status_code: str
    remain_access_count: str
    data: dict[str, Any]

    @property
    def remaining(self) -> int | None:
        try:
            return int(self.remain_access_count)
        except (TypeError, ValueError):
            return None


class JpoApiClient:
    """JPO 特許情報取得 API クライアント（トークン管理 + レートリミット付き）。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        mode: str | None = None,
        api_id: str | None = None,
        api_password: str | None = None,
        max_calls_per_minute: int | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.jpo_api_base_url).rstrip("/")
        self.mode = (mode or settings.jpo_api_mode).strip().lower()
        self.api_id = api_id if api_id is not None else settings.jpo_api_id.get_secret_value()
        self.api_password = (
            api_password
            if api_password is not None
            else settings.jpo_api_password.get_secret_value()
        )
        self.max_calls_per_minute = max_calls_per_minute or settings.jpo_api_max_calls_per_minute
        self._http = http_client
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0.0
        self._refresh_expires_at: float = 0.0
        # 固定ウィンドウ・レートリミッタ（1 分あたり max_calls_per_minute 回）。
        self._window_start: float = 0.0
        self._window_calls: int = 0

    # ------------------------------------------------------------------
    # プロパティ
    # ------------------------------------------------------------------

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo" or not (self.api_id and self.api_password)

    @property
    def mode_label(self) -> str:
        return "demo" if self.is_demo else "live"

    # ------------------------------------------------------------------
    # HTTP 基盤
    # ------------------------------------------------------------------

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={"User-Agent": "Construction-LegalOps-DX/1.0 (MVP)"},
            )
        return self._http

    async def _rate_limit_wait(self) -> None:
        """1 分あたりの呼び出し上限を守るため、必要なら待機する。"""
        if self.is_demo:
            return
        now = time.monotonic()
        if now - self._window_start >= 60.0:
            self._window_start = now
            self._window_calls = 0
        if self._window_calls >= self.max_calls_per_minute:
            wait = 60.0 - (now - self._window_start) + 0.1
            await asyncio.sleep(wait)
            self._window_start = time.monotonic()
            self._window_calls = 0
        self._window_calls += 1

    # ------------------------------------------------------------------
    # 認証
    # ------------------------------------------------------------------

    async def _ensure_token(self) -> str:
        """アクセストークンを返す。未取得・失効時は取得/リフレッシュする。"""
        if self.is_demo:
            return "demo-token"
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token
        if self._refresh_token and time.time() < self._refresh_expires_at:
            return await self._refresh()
        return await self._authenticate()

    async def _authenticate(self) -> str:
        client = self._http_client()
        try:
            resp = await client.post(
                f"{self.base_url}/auth/token",
                data={
                    "grant_type": "password",
                    "username": self.api_id,
                    "password": self.api_password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise JpoApiError(f"JPO token acquisition failed: {exc}") from exc
        payload = resp.json()
        self._apply_token_payload(payload)
        if not self._access_token:
            raise JpoApiError("JPO token response missing access_token")
        return self._access_token

    async def _refresh(self) -> str:
        client = self._http_client()
        try:
            resp = await client.post(
                f"{self.base_url}/auth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token or "",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise JpoApiError(f"JPO token refresh failed: {exc}") from exc
        payload = resp.json()
        self._apply_token_payload(payload)
        if not self._access_token:
            raise JpoApiError("JPO token refresh response missing access_token")
        return self._access_token

    def _apply_token_payload(self, payload: dict[str, Any]) -> None:
        self._access_token = payload.get("access_token")
        self._refresh_token = payload.get("refresh_token") or self._refresh_token
        expires_in = int(payload.get("expires_in", 3600))
        refresh_expires_in = int(payload.get("refresh_expires_in", 28800))
        self._token_expires_at = time.time() + expires_in
        self._refresh_expires_at = time.time() + refresh_expires_in

    # ------------------------------------------------------------------
    # API 呼び出し本体
    # ------------------------------------------------------------------

    async def call(
        self,
        *,
        domain: JpoDomain,
        api: str,
        case_number: str,
    ) -> JpoResult:
        """国内特許情報取得 API を 1 回呼び出し、成功結果を返す。

        statusCode=100 以外は ``JpoApiError``（日次上限は ``JpoRateLimitError``）。
        """
        if self.is_demo:
            return _demo_call(domain=domain, api=api, case_number=case_number)

        await self._rate_limit_wait()
        token = await self._ensure_token()
        prefix = _DOMAIN_PREFIX[domain]
        url = f"{self.base_url}/{prefix}/{api}/{quote(case_number, safe='')}"
        client = self._http_client()
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise JpoApiError(f"JPO API request failed ({domain}/{api}): {exc}") from exc

        content_type = resp.headers.get("content-type", "")
        if "zip" in content_type and "json" not in content_type:
            # 書類系 API の ZIP 実体は download_doc_zip() で取得する。
            # ここに ZIP が返るのは呼び出し種別の誤りなのでエラーにする。
            raise JpoApiError(
                f"JPO API returned non-JSON content ({resp.status_code}, {content_type})"
            )
        if resp.status_code == 429:
            raise JpoRateLimitError("JPO API daily quota exceeded (HTTP 429)")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise JpoApiError(f"JPO API returned invalid JSON ({resp.status_code})") from exc
        result = payload.get("result") or {}
        status_code = str(result.get("statusCode", ""))
        if status_code != "100":
            message = result.get("errorMessage") or f"statusCode={status_code}"
            if status_code in {"420", "429", "430"} or "上限" in str(message):
                raise JpoRateLimitError(f"JPO API quota: {message}")
            raise JpoApiError(f"JPO API error ({domain}/{api}): {message}")
        return JpoResult(
            status_code=status_code,
            remain_access_count=str(result.get("remainAccessCount", "")),
            data=result.get("data") or {},
        )

    # ------------------------------------------------------------------
    # 書類 ZIP の取得
    # ------------------------------------------------------------------

    async def download_doc_zip(
        self,
        *,
        domain: JpoDomain,
        api: str,
        case_number: str,
    ) -> bytes:
        """書類系 API（拒絶理由通知書等）の ZIP 実体を取得する。

        デモモードではダミー ZIP（XML 1 件入り）を返す。
        """
        if self.is_demo:
            return _demo_zip(domain=domain, api=api, case_number=case_number)

        await self._rate_limit_wait()
        token = await self._ensure_token()
        prefix = _DOMAIN_PREFIX[domain]
        url = f"{self.base_url}/{prefix}/{api}/{quote(case_number, safe='')}"
        client = self._http_client()
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise JpoApiError(f"JPO doc download failed ({api}): {exc}") from exc
        if resp.status_code == 429:
            raise JpoRateLimitError("JPO API daily quota exceeded (HTTP 429)")
        if resp.status_code != 200:
            # データが無い場合は JSON エラーレスポンスが返る。
            try:
                payload = resp.json()
                result = payload.get("result") or {}
                message = result.get("errorMessage") or f"statusCode={result.get('statusCode', '')}"
            except ValueError:
                message = f"HTTP {resp.status_code}"
            raise JpoApiError(f"JPO doc download failed ({api}): {message}")
        return resp.content


# ---------------------------------------------------------------------------
# ZIP / XML のユーティリティ
# ---------------------------------------------------------------------------


def extract_zip_text(zip_bytes: bytes, max_chars: int = 200_000) -> list[dict[str, str]]:
    """ZIP 内のテキスト（XML/HTM）を抽出して一覧で返す。

    各要素: ``{"name": ファイル名, "text": 抽出テキスト}``。バイナリ（PDF 等）は
    テキスト抽出対象外として ``text=""`` にする。
    """
    extracted: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                try:
                    raw = zf.read(name)
                except (RuntimeError, zipfile.BadZipFile):
                    continue
                text = _xml_bytes_to_text(raw)
                if text:
                    extracted.append({"name": name, "text": text[:max_chars]})
                else:
                    extracted.append({"name": name, "text": ""})
    except zipfile.BadZipFile:
        # デモ等で ZIP でないバイト列が渡された場合は、そのままテキストとして扱う。
        text = _xml_bytes_to_text(zip_bytes)
        if text:
            extracted.append({"name": "document", "text": text[:max_chars]})
    return extracted


def _xml_bytes_to_text(raw: bytes) -> str:
    """XML/HTM/テキストのバイト列からおおまかなテキストを取り出す。"""
    # まず UTF-8、ダメなら Shift-JIS 系を試す（JPO 書類は XML が中心）。
    content: str = ""
    for encoding in ("utf-8", "cp932", "euc-jp"):
        try:
            content = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return ""
    low = content.lower()
    if "<" in low and ">" in low and ("<?xml" in low or "<html" in low or "</" in low):
        # タグを除去（簡易）。スクリプト/スタイルは除外する。
        import re

        content = re.sub(r"(?is)<(script|style).*?</\1>", " ", content)
        content = re.sub(r"<[^>]+>", " ", content)
        content = content.replace("&lt;", "<").replace("&gt;", ">")
        content = content.replace("&amp;", "&").replace("&quot;", '"')
        content = content.replace("&#13;", " ").replace("\r", " ")
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# デモモード用の決定的データ
# ---------------------------------------------------------------------------

_DEMO_ASSETS: dict[str, dict[str, Any]] = {
    "2026000001": {
        "applicationNumber": "2026000001",
        "inventionTitle": "建設現場の安全管理システム（デモ）",
        "applicantAttorney": [
            {
                "applicantAttorneyCd": "000000001",
                "name": "みらい建設工業(株)",
                "applicantAttorneyClass": "1",
            }
        ],
        "filingDate": "20260115",
        "publicationNumber": "2026000001",
        "publicationDate": "20260701",
        "progress": [
            {
                "progressCode": "110",
                "progressDate": "20260115",
                "progressDetail": "出願",
            },
            {
                "progressCode": "160",
                "progressDate": "20260701",
                "progressDetail": "公開",
            },
            {
                "progressCode": "210",
                "progressDate": "20260720",
                "progressDetail": "審査請求",
            },
        ],
    },
    "2026000002": {
        "applicationNumber": "2026000002",
        "inventionTitle": "建設機械の遠隔監視装置（デモ）",
        "applicantAttorney": [
            {
                "applicantAttorneyCd": "000000001",
                "name": "みらい建設工業(株)",
                "applicantAttorneyClass": "1",
            }
        ],
        "filingDate": "20260210",
        "publicationNumber": "",
        "publicationDate": "",
        "progress": [
            {
                "progressCode": "110",
                "progressDate": "20260210",
                "progressDetail": "出願",
            },
        ],
    },
    "2026000003": {
        "applicationNumber": "2026000003",
        "inventionTitle": "コンクリート養生管理方法（デモ・競合）",
        "applicantAttorney": [
            {
                "applicantAttorneyCd": "000000002",
                "name": "さくら土木(株)",
                "applicantAttorneyClass": "1",
            }
        ],
        "filingDate": "20260305",
        "publicationNumber": "2026000002",
        "publicationDate": "20260801",
        "progress": [
            {
                "progressCode": "110",
                "progressDate": "20260305",
                "progressDetail": "出願",
            },
            {
                "progressCode": "160",
                "progressDate": "20260801",
                "progressDetail": "公開",
            },
            {
                "progressCode": "210",
                "progressDate": "20260810",
                "progressDetail": "審査請求",
            },
            {
                "progressCode": "300",
                "progressDate": "20260901",
                "progressDetail": "拒絶理由通知",
            },
        ],
    },
    "2026000004": {
        "applicationNumber": "2026000004",
        "inventionTitle": "橋梁点検用ドローンシステム（デモ・競合）",
        "applicantAttorney": [
            {
                "applicantAttorneyCd": "000000002",
                "name": "さくら土木(株)",
                "applicantAttorneyClass": "1",
            }
        ],
        "filingDate": "20260401",
        "publicationNumber": "",
        "publicationDate": "",
        "progress": [
            {
                "progressCode": "110",
                "progressDate": "20260401",
                "progressDetail": "出願",
            },
        ],
    },
}

_DEMO_CODES: dict[str, list[dict[str, str]]] = {
    "みらい建設工業": [{"applicantAttorneyCd": "000000001", "name": "みらい建設工業(株)"}],
    "さくら土木": [{"applicantAttorneyCd": "000000002", "name": "さくら土木(株)"}],
    "株式会社つばさ組": [{"applicantAttorneyCd": "000000003", "name": "(株)つばさ組"}],
}

_DEMO_REGISTRATION: dict[str, dict[str, Any]] = {
    "2026000001": {
        "applicationNumber": "2026000001",
        "registrationNumber": "7000001",
        "registrationDate": "20260930",
        "rightPersonInformation": [
            {"rightPersonCd": "000000001", "rightPersonName": "みらい建設工業(株)"}
        ],
    }
}

_DEMO_CASE_REFERENCE = {
    "applicationNumber": "2026000001",
    "publicationNumber": "2026000001",
    "registrationNumber": "7000001",
}

_DEMO_CITATIONS = {
    "patentDoc": [
        {
            "draftDate": "20260901",
            "citationType": "01",
            "citationOrder": "1",
            "documentNumber": "JP2020-123456A",
        }
    ],
    "nonPatentDoc": [
        {
            "draftDate": "20260901",
            "citationType": "02",
            "citationOrder": "2",
            "documentName": "建設工事の品質管理便覧（デモ）",
        }
    ],
}

_DEMO_JPP_URL = "https://www.j-platpat.inpit.go.jp/c1800/PU/JP-2026-000001/15/ja"

_DEMO_DIVISIONAL = {
    "applicationNumber": "2026000001",
    "parentApplicationInformation": [],
    "divisionalApplicationInformation": [],
}

_DEMO_DOCS = {
    "refusal_reason": (
        "拒絶理由通知書（デモ）\n"
        "【通知日】2026年9月1日\n"
        "【出願番号】2026000003\n"
        "【発明の名称】コンクリート養生管理方法\n"
        "【拒絶理由】\n"
        "1. 特許法第29条第1項第3号（新規性）\n"
        "   引用文献1（JP2020-123456A）に記載された発明と同一である。\n"
        "2. 特許法第29条第2項（進歩性）\n"
        "   引用文献1および引用文献2（非特許文献）に基づいて当業者が容易に発明できた。\n"
        "【指定期間】この通知の発送の日から3月以内に意見書又は補正書を提出すること。\n"
    ),
    "opinion_amendment": (
        "意見書（デモ）\n"
        "【提出日】2026年9月20日\n"
        "【出願番号】2026000003\n"
        "【発明の名称】コンクリート養生管理方法\n"
        "【意見】\n"
        "拒絶理由のうち進歩性欠如の指摘について、本願発明は引用文献には記載のない構成を有する。\n"
    ),
    "decision": (
        "特許査定（デモ）\n"
        "【査定日】2026年10月15日\n"
        "【出願番号】2026000001\n"
        "【発明の名称】建設現場の安全管理システム\n"
        "【査定の結論】特許を査定する。\n"
    ),
}


def _demo_call(*, domain: JpoDomain, api: str, case_number: str) -> JpoResult:
    """デモモード用: API 種別に応じた決定的なデータを返す。"""
    data: dict[str, Any]
    asset = _DEMO_ASSETS.get(case_number)
    if api == "app_progress":
        if asset is None:
            data = {"applicationNumber": case_number, "progress": []}
        else:
            data = {k: v for k, v in asset.items() if k != "progress"}
            data["progress"] = asset["progress"]
    elif api == "app_progress_simple":
        data = _demo_call(domain=domain, api="app_progress", case_number=case_number).data
    elif api == "registration_info":
        data = _DEMO_REGISTRATION.get(
            case_number,
            {"applicationNumber": case_number},
        )
    elif api == "case_number_reference":
        data = dict(_DEMO_CASE_REFERENCE)
        data["applicationNumber"] = case_number
    elif api == "cite_doc_info":
        data = dict(_DEMO_CITATIONS)
        data["applicationNumber"] = case_number
    elif api == "jpp_fixed_address":
        data = {"URL": _DEMO_JPP_URL}
    elif api == "divisional_app_info":
        data = dict(_DEMO_DIVISIONAL)
        data["applicationNumber"] = case_number
    elif api == "priority_right_app_info":
        data = {"applicationNumber": case_number, "priorityRightApplicationInformation": []}
    elif api == "applicant_attorney":
        rows = _DEMO_CODES.get(case_number)
        data = {
            "applicantAttorney": (
                rows
                if rows is not None
                else [{"applicantAttorneyCd": "000000009", "name": case_number}]
            )
        }
    elif api == "applicant_attorney_cd":
        name = next(
            (
                r["name"]
                for rows in _DEMO_CODES.values()
                for r in rows
                if r["applicantAttorneyCd"] == case_number
            ),
            "デモ申請人",
        )
        data = {"applicantAttorney": [{"applicantAttorneyCd": case_number, "name": name}]}
    else:
        data = {"applicationNumber": case_number}
    return JpoResult(status_code="100", remain_access_count="399", data=data)


def _demo_zip(*, domain: JpoDomain, api: str, case_number: str) -> bytes:
    """デモモード用: 書類種別に応じたダミー XML を含む ZIP を返す。"""
    if api == "app_doc_cont_refusal_reason":
        doc = _DEMO_DOCS["refusal_reason"]
    elif api == "app_doc_cont_opinion_amendment":
        doc = _DEMO_DOCS["opinion_amendment"]
    elif api == "app_doc_cont_refusal_reason_decision":
        doc = _DEMO_DOCS["decision"]
    else:
        doc = "書類（デモ）\n"
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Document><Content>{doc}</Content></Document>'
    ).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"doc_{api}.xml", xml)
    return buf.getvalue()


__all__ = [
    "IpType",
    "JpoApiClient",
    "JpoApiError",
    "JpoDomain",
    "JpoRateLimitError",
    "JpoResult",
    "extract_zip_text",
]
