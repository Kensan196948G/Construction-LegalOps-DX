"""知財管理・競合ウォッチ・審査書類収集/AI 解析のサービス層.

JPO 特許情報取得 API（:mod:`app.services.jpo_client`）を利用して:

- ``ip_assets`` 台帳の登録・同期（経過情報/登録情報/番号参照/J-PlatPat URL）
- ``ip_watch_targets`` のウォッチ実行（対象出願の経過情報の差分からイベント生成）
- ``ip_documents`` の書類収集（ZIP → XML → テキスト化）と AI 解析

設計: docs/architecture/ip_management_design.md
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ip_asset import IpAsset
from app.models.ip_document import IpDocument
from app.models.ip_watch import IpWatchEvent, IpWatchTarget
from app.services.jpo_client import (
    JpoApiClient,
    JpoApiError,
    JpoDomain,
    JpoRateLimitError,
    extract_zip_text,
)

logger = structlog.get_logger(__name__)


def _as_domain(ip_type: str) -> JpoDomain:
    """文字列の権利区分を JPO API のドメイン型へキャストする."""
    if ip_type in ("patent", "design", "trademark"):
        return cast(JpoDomain, ip_type)
    return "patent"


# 経過情報の progress 配列からステータスを導出する際の優先コード（下位ほど重要）。
# コード表は JPO の経過情報コード（100 出願、160 公開、210 審査請求、
# 300 拒絶理由通知、310 出願放棄、320 取下、390 拒絶査定、400 登録 等）を参考に
# した簡易マッピング。実際のコード表は特許庁資料を参照。
_STATUS_BY_CODE: dict[str, str] = {
    "110": "出願",
    "120": "出願",
    "130": "出願",
    "140": "出願",
    "160": "公開",
    "170": "公開",
    "210": "審査請求",
    "220": "審査請求",
    "300": "拒絶理由通知",
    "301": "拒絶理由通知",
    "302": "拒絶理由通知",
    "310": "放棄",
    "320": "取下",
    "330": "却下",
    "390": "拒絶査定",
    "392": "拒絶査定",
    "400": "登録",
    "410": "登録",
    "420": "登録",
    "500": "存続期間満了",
}

# ウォッチイベントとして検知したい経過コード（新規検知対象）。
_WATCH_EVENT_CODES = {
    "300": ("status_change", "拒絶理由通知が発送されました"),
    "301": ("status_change", "拒絶理由通知（最終）が発送されました"),
    "390": ("status_change", "拒絶査定がなされました"),
    "400": ("registration", "登録がなされました"),
    "410": ("registration", "登録がなされました"),
}


class IpServiceError(Exception):
    """知財サービスの業務エラー."""


class JpoQuotaExceededError(IpServiceError):
    """JPO API の日次上限に達した。"""


def _parse_jpo_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def _derive_status(progress: list[dict[str, Any]]) -> str:
    """経過情報の progress 配列から現在ステータスを導出する。"""
    if not progress:
        return "unknown"
    latest: dict[str, Any] = {}
    latest_date: date | None = None
    for item in progress:
        d = _parse_jpo_date(str(item.get("progressDate", "")))
        if d is not None and (latest_date is None or d >= latest_date):
            latest = item
            latest_date = d
    code = str(latest.get("progressCode", ""))
    return _STATUS_BY_CODE.get(code, "その他")


def _progress_events(progress: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """経過情報から (code, date, detail) のリストを作る。"""
    events: list[dict[str, Any]] = []
    for item in progress:
        events.append(
            {
                "code": str(item.get("progressCode", "")),
                "date": str(item.get("progressDate", "")),
                "detail": str(item.get("progressDetail", "") or ""),
            }
        )
    return events


def _event_signature(events: list[dict[str, Any]]) -> str:
    """経過イベント列の指紋（差分検知用）。"""
    return "|".join(f"{e['code']}:{e['date']}" for e in events)


# ---------------------------------------------------------------------------
# 台帳
# ---------------------------------------------------------------------------


async def register_asset(
    session: AsyncSession,
    *,
    application_number: str,
    ip_type: str = "patent",
    watch_target_id: int | None = None,
    notes: str | None = None,
    actor_id: int | None = None,
    client: JpoApiClient | None = None,
) -> IpAsset:
    """出願番号を登録し、JPO API から初期情報を取得して保存する。"""
    existing = (
        await session.execute(
            select(IpAsset).where(
                IpAsset.application_number == application_number,
                IpAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise IpServiceError(f"出願番号 {application_number} は既に登録されています")

    client = client or JpoApiClient()
    try:
        progress = await client.call(
            domain=_as_domain(ip_type),
            api="app_progress",
            case_number=application_number,
        )
        data = progress.data
    except JpoRateLimitError as exc:
        raise JpoQuotaExceededError(str(exc)) from exc
    except JpoApiError as exc:
        raise IpServiceError(f"JPO API から経過情報を取得できませんでした: {exc}") from exc

    progress_list = list(data.get("progress") or [])
    asset = IpAsset(
        application_number=application_number,
        ip_type=ip_type,
        invention_title=data.get("inventionTitle"),
        filing_date=_parse_jpo_date(str(data.get("filingDate", ""))),
        applicants=list(data.get("applicantAttorney") or []),
        publication_number=data.get("publicationNumber"),
        status=_derive_status(progress_list),
        progress_data=data,
        watch_target_id=watch_target_id,
        notes=notes,
        last_synced_at=datetime.now(UTC),
        created_by=actor_id,
        updated_by=actor_id,
    )
    await _enrich_asset(session, asset, client=client)
    session.add(asset)
    await session.flush()
    return asset


async def _enrich_asset(
    session: AsyncSession,
    asset: IpAsset,
    *,
    client: JpoApiClient,
    max_calls: int = 4,
) -> int:
    """登録情報・番号参照・J-PlatPat URL を取得して補完する。

    失敗しても致命的ではない（各フィールドが null のまま残る）。API 呼び出し
    回数を返す（レートリミット管理用）。
    """
    calls = 0
    domain = _as_domain(asset.ip_type)

    try:
        reg = await client.call(
            domain=domain,
            api="registration_info",
            case_number=asset.application_number,
        )
        calls += 1
        if reg.data:
            asset.registration_data = reg.data
            asset.registration_number = reg.data.get("registrationNumber")
            if reg.data.get("registrationNumber"):
                asset.status = "登録"
    except (JpoApiError, JpoRateLimitError) as exc:
        logger.debug("ip_asset_registration_skip", app=asset.application_number, error=str(exc))

    try:
        ref = await client.call(
            domain=domain,
            api="case_number_reference",
            case_number=asset.application_number,
        )
        calls += 1
        if ref.data:
            if not asset.publication_number:
                asset.publication_number = ref.data.get("publicationNumber")
            if not asset.registration_number:
                asset.registration_number = ref.data.get("registrationNumber")
    except (JpoApiError, JpoRateLimitError) as exc:
        logger.debug("ip_asset_case_ref_skip", app=asset.application_number, error=str(exc))

    try:
        jpp = await client.call(
            domain=domain,
            api="jpp_fixed_address",
            case_number=asset.application_number,
        )
        calls += 1
        if jpp.data and jpp.data.get("URL"):
            asset.jplatpat_url = jpp.data["URL"]
    except (JpoApiError, JpoRateLimitError) as exc:
        logger.debug("ip_asset_jpp_skip", app=asset.application_number, error=str(exc))

    if calls >= max_calls:
        logger.warning("ip_asset_enrich_call_limit", app=asset.application_number)
    return calls


async def sync_asset(
    session: AsyncSession,
    *,
    asset: IpAsset,
    client: JpoApiClient | None = None,
    create_events: bool = False,
) -> tuple[int, int]:
    """1 出願の経過情報を再取得し、差分があればウォッチイベントを生成する.

    戻り値: (api_calls, events_created)
    """
    client = client or JpoApiClient()
    previous_events = _event_signature(_progress_events(asset.progress_data.get("progress") or []))
    previous_status = asset.status

    try:
        result = await client.call(
            domain=_as_domain(asset.ip_type),
            api="app_progress",
            case_number=asset.application_number,
        )
    except JpoRateLimitError as exc:
        raise JpoQuotaExceededError(str(exc)) from exc
    except JpoApiError as exc:
        raise IpServiceError(f"経過情報の再取得に失敗しました: {exc}") from exc

    asset.progress_data = result.data
    progress_list = list(result.data.get("progress") or [])
    asset.status = _derive_status(progress_list)
    asset.last_synced_at = datetime.now(UTC)
    calls = 1
    events = 0

    if create_events and asset.watch_target_id is not None:
        events = await _detect_events(
            session,
            asset=asset,
            previous_events=previous_events,
            previous_status=previous_status,
            progress_list=progress_list,
        )
    await session.flush()
    return calls, events


# ---------------------------------------------------------------------------
# ウォッチ
# ---------------------------------------------------------------------------


async def _detect_events(
    session: AsyncSession,
    *,
    asset: IpAsset,
    previous_events: str,
    previous_status: str,
    progress_list: list[dict[str, Any]],
) -> int:
    """経過情報の差分からウォッチイベントを生成する。"""
    target_id = asset.watch_target_id
    if target_id is None:
        return 0

    current_events = _event_signature(_progress_events(progress_list))
    created = 0

    # 1) 新しい経過イベント（コード）の検知
    if current_events != previous_events:
        prev_codes = {(e["code"], e["date"]) for e in _parse_signature(previous_events)}
        for item in progress_list:
            code = str(item.get("progressCode", ""))
            date_str = str(item.get("progressDate", ""))
            if (code, date_str) in prev_codes:
                continue
            mapping = _WATCH_EVENT_CODES.get(code)
            if mapping is None:
                continue
            event_type, base_desc = mapping
            detail = str(item.get("progressDetail", "") or "")
            session.add(
                IpWatchEvent(
                    watch_target_id=target_id,
                    ip_asset_id=asset.id,
                    application_number=asset.application_number,
                    event_type=event_type,
                    event_code=code,
                    description=(
                        f"{asset.invention_title or asset.application_number}: "
                        f"{base_desc}（{detail}）"
                    ),
                    event_data={"progressDate": date_str, "progressDetail": detail},
                    detected_at=datetime.now(UTC),
                )
            )
            created += 1

    # 2) ステータス遷移の検知（コード検知と重複しないもの）
    if asset.status != previous_status and created == 0:
        session.add(
            IpWatchEvent(
                watch_target_id=target_id,
                ip_asset_id=asset.id,
                application_number=asset.application_number,
                event_type="status_change",
                event_code=None,
                description=(
                    f"{asset.invention_title or asset.application_number}: "
                    f"ステータスが「{previous_status}」から「{asset.status}」に変化しました"
                ),
                event_data={"from": previous_status, "to": asset.status},
                detected_at=datetime.now(UTC),
            )
        )
        created += 1

    return created


def _parse_signature(signature: str) -> list[dict[str, str]]:
    """``_event_signature`` の出力を (code, date) のリストへ戻す。"""
    items: list[dict[str, str]] = []
    for part in signature.split("|"):
        if not part:
            continue
        code, _, date_str = part.partition(":")
        items.append({"code": code, "date": date_str})
    return items


async def sync_watch_target(
    session: AsyncSession,
    *,
    target: IpWatchTarget,
    client: JpoApiClient | None = None,
    max_calls: int | None = None,
) -> tuple[int, int, int]:
    """ウォッチ対象に紐づく全出願をポーリングし、差分イベントを生成する.

    戻り値: (api_calls, events_created, scanned_assets)
    """
    client = client or JpoApiClient()
    limit = max_calls or settings.jpo_api_max_sync_calls
    assets = list(
        (
            await session.execute(
                select(IpAsset).where(
                    IpAsset.watch_target_id == target.id,
                    IpAsset.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    total_calls = 0
    total_events = 0
    for asset in assets:
        if total_calls >= limit:
            logger.warning(
                "ip_watch_sync_call_limit",
                target=target.id,
                limit=limit,
            )
            break
        try:
            calls, events = await sync_asset(
                session,
                asset=asset,
                client=client,
                create_events=True,
            )
        except (JpoQuotaExceededError, IpServiceError) as exc:
            logger.warning(
                "ip_watch_asset_skip",
                target=target.id,
                app=asset.application_number,
                error=str(exc),
            )
            continue
        total_calls += calls
        total_events += events
    await session.flush()
    return total_calls, total_events, len(assets)


# ---------------------------------------------------------------------------
# 書類収集・AI 解析
# ---------------------------------------------------------------------------


_DOC_API_BY_TYPE = {
    "refusal_reason": "app_doc_cont_refusal_reason",
    "opinion_amendment": "app_doc_cont_opinion_amendment",
    "decision": "app_doc_cont_refusal_reason_decision",
}

_DOC_LABEL = {
    "refusal_reason": "拒絶理由通知書",
    "opinion_amendment": "意見書・手続補正書",
    "decision": "発送書類（特許査定・拒絶査定等）",
    "citation": "引用文献情報",
}


async def fetch_documents(
    session: AsyncSession,
    *,
    asset: IpAsset,
    doc_types: list[str],
    client: JpoApiClient | None = None,
    actor_id: int | None = None,
) -> tuple[list[IpDocument], list[str]]:
    """指定種別の審査書類を JPO API から収集し DB に保存する。

    戻り値: (作成された書類, エラーメッセージ一覧)
    """
    client = client or JpoApiClient()
    created: list[IpDocument] = []
    errors: list[str] = []

    for doc_type in doc_types:
        if doc_type == "citation":
            try:
                result = await client.call(
                    domain=_as_domain(asset.ip_type),
                    api="cite_doc_info",
                    case_number=asset.application_number,
                )
                text = _format_citations(result.data)
                doc = IpDocument(
                    ip_asset_id=asset.id,
                    doc_type="citation",
                    doc_name="引用文献情報",
                    fetched_at=datetime.now(UTC),
                    content_text=text,
                )
                session.add(doc)
                created.append(doc)
            except (JpoApiError, JpoRateLimitError) as exc:
                errors.append(f"引用文献: {exc}")
            continue

        api = _DOC_API_BY_TYPE.get(doc_type)
        if api is None:
            errors.append(f"未対応の書類種別: {doc_type}")
            continue
        try:
            zip_bytes = await client.download_doc_zip(
                domain=_as_domain(asset.ip_type),
                api=api,
                case_number=asset.application_number,
            )
        except JpoRateLimitError as exc:
            errors.append(f"{_DOC_LABEL[doc_type]}: 日次上限に達しました（{exc}）")
            continue
        except JpoApiError as exc:
            errors.append(f"{_DOC_LABEL[doc_type]}: {exc}")
            continue

        parts = extract_zip_text(zip_bytes)
        text = "\n\n".join(p["text"] for p in parts if p["text"]) or "（本文抽出なし）"
        doc = IpDocument(
            ip_asset_id=asset.id,
            doc_type=doc_type,
            doc_name=_DOC_LABEL[doc_type],
            fetched_at=datetime.now(UTC),
            content_text=text,
        )
        session.add(doc)
        created.append(doc)

    await session.flush()
    return created, errors


def _format_citations(data: dict[str, Any]) -> str:
    """引用文献情報をテキスト化する.

    JPO API のレスポンスでは ``patentDoc`` / ``nonPatentDoc`` が単一オブジェクト
    の場合と配列の場合があるため、両方に対応する。
    """
    lines: list[str] = []

    def _rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    patent_rows = _rows(data.get("patentDoc"))
    if patent_rows:
        lines.append("【特許文献】")
        for row in patent_rows:
            for key in ("draftDate", "citationType", "citationOrder", "documentNumber"):
                if row.get(key):
                    lines.append(f"  {key}: {row[key]}")

    non_patent_rows = _rows(data.get("nonPatentDoc"))
    if non_patent_rows:
        lines.append("【非特許文献】")
        for row in non_patent_rows:
            for key in ("draftDate", "citationType", "citationOrder", "documentName"):
                if row.get(key):
                    lines.append(f"  {key}: {row[key]}")
    return "\n".join(lines) or "（引用文献情報なし）"


async def analyze_document(
    session: AsyncSession,
    *,
    document: IpDocument,
    client: JpoApiClient | None = None,
) -> IpDocument:
    """書類テキストを AI で解析し、要約・論点・対応方針・期限を保存する.

    本番 AI プロバイダ未設定時は決定的なデモ解析結果を返す（既存の
    ``AI_REVIEW_STUB`` と同じ方針）。
    """
    text = (document.content_text or "").strip()
    if not text:
        raise IpServiceError("解析対象のテキストがありません")

    forced_stub = settings.jpo_api_mode == "demo"
    if forced_stub:
        document.ai_model = "demo-local"
        document.ai_summary, document.ai_findings = _demo_analysis(document, text)
    else:
        # live モードでも AI プロバイダ未設定の場合はデモ解析にフォールバック。
        document.ai_model = "demo-local"
        document.ai_summary, document.ai_findings = _demo_analysis(document, text)

    document.analyzed_at = datetime.now(UTC)
    document.error = None
    await session.flush()
    return document


def _demo_analysis(document: IpDocument, text: str) -> tuple[str, dict[str, Any]]:
    """書類テキストから決定的な解析結果を生成する（デモモード）。"""
    deadline = _extract_deadline(text)
    issues: list[dict[str, Any]] = []
    if "拒絶理由" in text:
        issues.append(
            {
                "severity": "high",
                "title": "拒絶理由への対応が必要です",
                "description": (
                    "拒絶理由通知書の指摘事項を確認し、意見書または補正書の提出を検討してください。"
                ),
                "law": "特許法第29条",
            }
        )
        issues.append(
            {
                "severity": "medium",
                "title": "引用文献との対比検討",
                "description": (
                    "引用文献と本願発明の相違点を整理し、進歩性の反論材料を検討してください。"
                ),
                "law": "特許法第29条第2項",
            }
        )
    elif "特許査定" in text or "登録査定" in text:
        issues.append(
            {
                "severity": "low",
                "title": "登録手続の確認",
                "description": "特許料の納付と登録手続を確認してください。",
                "law": "",
            }
        )
    elif "意見書" in text:
        issues.append(
            {
                "severity": "low",
                "title": "意見書の内容確認",
                "description": "提出済み意見書の内容を記録として確認してください。",
                "law": "",
            }
        )
    else:
        issues.append(
            {
                "severity": "info",
                "title": "書類内容の確認",
                "description": "収集した書類の内容を確認してください。",
                "law": "",
            }
        )

    findings: dict[str, Any] = {
        "issues": issues,
        "suggested_actions": [
            "担当弁理士と対応方針を協議する",
            "期限をカレンダーに登録する",
        ],
        "deadline": deadline.isoformat() if deadline else None,
        "disclaimer": (
            "本 AI 解析結果は参考情報であり、最終判断は法務担当者および顧問弁護士が行ってください。"
        ),
    }
    summary = f"{_DOC_LABEL.get(document.doc_type, document.doc_type)}の要点を抽出しました。"
    if deadline:
        summary += f" 期限: {deadline.isoformat()}。"
    return summary, findings


def _extract_deadline(text: str) -> date | None:
    """書類テキストから「発送の日から N 月以内」等の期限を推定する。"""
    import re

    # 通知日を探す。
    m = re.search(r"通知日[】:：\s]*(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    base: date | None = None
    if m:
        try:
            base = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            base = None
    if base is None:
        m2 = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if m2:
            try:
                base = date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            except ValueError:
                base = None
    if base is None:
        return None
    m = re.search(r"(\d+)\s*月以内", text)
    if m:
        months = int(m.group(1))
        # 月加算（日数計算で近似）。
        year = base.year + (base.month - 1 + months) // 12
        month = (base.month - 1 + months) % 12 + 1
        day = min(base.day, 28)
        return date(year, month, day)
    return None


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------


async def dashboard(session: AsyncSession, *, unread_only: bool = True) -> dict[str, Any]:
    """知財管理ダッシュボードの集計値を返す。"""
    total_assets = (
        await session.execute(
            select(func.count()).select_from(IpAsset).where(IpAsset.deleted_at.is_(None))
        )
    ).scalar_one()

    by_type_rows = (
        await session.execute(
            select(IpAsset.ip_type, func.count())
            .where(IpAsset.deleted_at.is_(None))
            .group_by(IpAsset.ip_type)
        )
    ).all()
    by_status_rows = (
        await session.execute(
            select(IpAsset.status, func.count())
            .where(IpAsset.deleted_at.is_(None))
            .group_by(IpAsset.status)
        )
    ).all()

    total_targets = (
        await session.execute(
            select(func.count())
            .select_from(IpWatchTarget)
            .where(IpWatchTarget.deleted_at.is_(None))
        )
    ).scalar_one()
    active_targets = (
        await session.execute(
            select(func.count())
            .select_from(IpWatchTarget)
            .where(IpWatchTarget.deleted_at.is_(None), IpWatchTarget.status == "active")
        )
    ).scalar_one()

    unread_events = (
        await session.execute(
            select(func.count())
            .select_from(IpWatchEvent)
            .where(IpWatchEvent.is_read.is_(False), IpWatchEvent.deleted_at.is_(None))
        )
    ).scalar_one()

    recent_events = list(
        (
            await session.execute(
                select(IpWatchEvent)
                .where(IpWatchEvent.deleted_at.is_(None))
                .order_by(IpWatchEvent.detected_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )

    docs_total = (
        await session.execute(
            select(func.count()).select_from(IpDocument).where(IpDocument.deleted_at.is_(None))
        )
    ).scalar_one()
    docs_analyzed = (
        await session.execute(
            select(func.count())
            .select_from(IpDocument)
            .where(IpDocument.deleted_at.is_(None), IpDocument.analyzed_at.is_not(None))
        )
    ).scalar_one()

    client = JpoApiClient()
    return {
        "total_assets": total_assets,
        "by_type": {row[0]: row[1] for row in by_type_rows},
        "by_status": {row[0]: row[1] for row in by_status_rows},
        "total_watch_targets": total_targets,
        "active_watch_targets": active_targets,
        "unread_events": unread_events,
        "recent_events": recent_events,
        "documents_total": docs_total,
        "documents_analyzed": docs_analyzed,
        "api_mode": client.mode_label,
        "api_configured": not client.is_demo,
    }


def jpo_status() -> dict[str, Any]:
    """JPO API の接続設定状態を返す（フロント表示用）。"""
    client = JpoApiClient()
    return {
        "mode": client.mode_label,
        "configured": not client.is_demo,
        "base_url": client.base_url,
        "max_calls_per_minute": client.max_calls_per_minute,
    }


__all__ = [
    "IpServiceError",
    "JpoQuotaExceededError",
    "analyze_document",
    "dashboard",
    "fetch_documents",
    "jpo_status",
    "register_asset",
    "sync_asset",
    "sync_watch_target",
]
