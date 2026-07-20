"""AI contract review service.

Wraps the Anthropic Claude API to produce a structured contract-review
result that downstream services (risk scoring, workflow engine) can
consume. The service obeys the policies in:

* ``docs/contract_review_policy.md`` — what to inspect per contract type.
* ``docs/risk_scoring_policy.md`` — issue code catalog for additive scoring.
* ``docs/ai_disclaimer_policy.md`` — masking, logging, AI-as-aid stance.

Two run modes are supported, selectable via ``AI_REVIEW_MODE``:

* ``stub`` (default for Loop 2 / unit tests) — deterministic heuristic
  output with no external network call.
* ``real`` — calls Claude via the official ``anthropic`` async SDK with
  tenacity-driven retry and a lightweight circuit breaker.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, cast

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.models.enums import RiskLevel
from app.services.sensitive_detector import SensitiveDetector

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReviewIssue:
    """A single finding produced by the AI reviewer."""

    code: str
    title: str
    severity: RiskLevel
    description: str
    clause_reference: str | None = None
    recommended_action: str | None = None
    citations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AIReviewResult:
    """Structured output of :meth:`AIReviewService.review_contract`."""

    contract_type: str
    summary: str
    issues: list[ReviewIssue]
    overall_risk: RiskLevel
    model_id: str
    prompt_template_id: str
    masked_input_length: int
    detections_redacted: int
    elapsed_ms: int
    mode: str  # "stub" | "real"
    generated_at: str  # ISO-8601 UTC
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["issues"] = [
            {**asdict(i), "severity": i.severity.value} for i in self.issues
        ]
        data["overall_risk"] = self.overall_risk.value
        return data


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCLAIMER: Final[str] = (
    "本結果は AI による補助出力です。契約締結可否は人間（法務担当者・"
    "法務課長・管理本部長・顧問弁護士）が最終判断します。"
)

PROMPT_TEMPLATE_ID: Final[str] = "contract_review.v1"

_SYSTEM_PROMPT: Final[str] = (
    "あなたは日本の建設業（公共工事 8 割／民間 2 割）に特化した法務レビュー補助 AI です。"
    "出力は必ず JSON で行い、`summary`, `overall_risk`, `issues` の 3 キーを含めてください。"
    "`overall_risk` は low/medium/high/critical のいずれか。`issues[*].code` は"
    "社内リスクスコアリング辞書のコード（例: no_liability_cap, missing_antisocial_clause）"
    "を用いてください。建設業法、下請法、個人情報保護法、電子帳簿保存法、反社条項、"
    "贈収賄関連を必ず点検対象に含めてください。AI は補助であり、最終判断は人間が行うため、"
    "断定的な合意可否の判断は避け、リスク要因の列挙と推奨アクションの提示に留めてください。"
)


# ---------------------------------------------------------------------------
# Lightweight in-process circuit breaker
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _CircuitBreaker:
    """A trivial closed→open→half-open state machine.

    The breaker is process-local; in production a Redis-backed shared
    breaker would be wired in via :func:`get_settings`. For Loop 2 the
    in-process version is sufficient.
    """

    failure_threshold: int = 5
    recovery_seconds: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        # half-open: allow a probe call after recovery window
        return time.monotonic() - self._opened_at >= self.recovery_seconds

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()


class AIReviewServiceError(RuntimeError):
    """Raised when the AI reviewer cannot produce a result."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AIReviewService:
    """High-level façade for contract review.

    Dependencies are injected via the constructor so unit tests can pass a
    fake Anthropic client and a stub detector without monkey-patching.
    """

    def __init__(
        self,
        *,
        mode: str | None = None,
        anthropic_client: Any | None = None,
        detector: SensitiveDetector | None = None,
        model_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self._mode = (mode or os.getenv("AI_REVIEW_MODE", "stub") or "stub").lower()
        self._api_key = settings.claude_api_key.get_secret_value()
        if settings.is_production:
            if self._mode == "stub":
                raise RuntimeError("AI_REVIEW_MODE=stub is disabled when APP_ENV=production")
            if self._api_key == "sk-ant-replace-me" or not self._api_key.startswith("sk-ant-"):
                raise RuntimeError(
                    "CLAUDE_API_KEY must be configured when APP_ENV=production"
                )
        self._client = anthropic_client
        self._detector = detector or SensitiveDetector()
        self._model_id = model_id or settings.claude_model
        self._max_tokens = settings.claude_max_tokens
        self._timeout = settings.claude_timeout_seconds
        self._breaker = _CircuitBreaker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def review_contract(
        self, text: str, contract_type: str
    ) -> AIReviewResult:
        """Return a structured AI review for ``text`` of ``contract_type``."""
        if not text or not text.strip():
            raise AIReviewServiceError("contract text is empty")

        started = time.perf_counter()
        detections = self._detector.detect(text)
        masked_text = self._detector.mask(text, detections)
        logger.info(
            "ai_review.start",
            contract_type=contract_type,
            mode=self._mode,
            text_chars=len(text),
            masked_chars=len(masked_text),
            redactions=len(detections),
        )

        if self._mode == "stub" or not self._api_key.startswith("sk-ant-"):
            raw = self._stub_payload(masked_text, contract_type)
        else:
            if not self._breaker.allow():
                logger.warning("ai_review.circuit_open", model=self._model_id)
                raise AIReviewServiceError("AI reviewer circuit breaker is open")
            try:
                raw = await self._call_claude(masked_text, contract_type)
                self._breaker.record_success()
            except Exception as exc:  # pragma: no cover - real path
                self._breaker.record_failure()
                logger.error("ai_review.failed", error=str(exc))
                raise AIReviewServiceError(str(exc)) from exc

        result = self._build_result(
            raw=raw,
            contract_type=contract_type,
            masked_len=len(masked_text),
            redactions=len(detections),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        logger.info(
            "ai_review.complete",
            contract_type=contract_type,
            mode=self._mode,
            issues=len(result.issues),
            overall_risk=result.overall_risk.value,
            elapsed_ms=result.elapsed_ms,
        )
        return result

    # ------------------------------------------------------------------
    # Stub-mode implementation
    # ------------------------------------------------------------------

    def _stub_payload(self, masked_text: str, contract_type: str) -> dict[str, Any]:
        """Deterministic heuristic stub output.

        The stub inspects ``masked_text`` for a handful of well-known
        Japanese contract patterns and emits the matching ``ISSUE_WEIGHTS``
        codes. The result is realistic enough that downstream risk
        scoring and workflow routing produce non-trivial values.
        """
        issues: list[dict[str, Any]] = []

        def add(code: str, title: str, sev: RiskLevel, desc: str,
                clause: str | None = None, action: str | None = None) -> None:
            issues.append(
                {
                    "code": code,
                    "title": title,
                    "severity": sev.value,
                    "description": desc,
                    "clause_reference": clause,
                    "recommended_action": action,
                    "citations": [],
                }
            )

        t = masked_text

        # 損害賠償上限
        if not re.search(r"損害賠償.{0,30}上限", t) and "損害賠償" in t:
            add(
                "no_liability_cap",
                "損害賠償上限の定めなし",
                RiskLevel.HIGH,
                "損害賠償の上限額・範囲が明示されていない懸念があります。",
                action="契約金額の 30% 程度を上限として明記してください。",
            )

        # 反社条項
        if not re.search(r"反社会的勢力|暴力団排除", t):
            add(
                "missing_antisocial_clause",
                "反社条項の欠落",
                RiskLevel.CRITICAL,
                "反社会的勢力排除条項が見当たりません。",
                action="社内雛形の反社条項を追記してください。",
            )
        else:
            add(
                "complete_antisocial_clause",
                "反社条項あり",
                RiskLevel.LOW,
                "反社条項が確認できました。",
            )

        # 個人情報・マイナンバー
        if "<MY_NUMBER>" in t or "マイナンバー" in t:
            add(
                "handles_my_number",
                "マイナンバーの取扱い",
                RiskLevel.HIGH,
                "マイナンバーの取扱条項が必要です。",
                action="マイナンバー法に基づく安全管理措置条項を追加してください。",
            )

        # 再委託
        if re.search(r"再委託.{0,20}(自由|制限なし|承諾不要)", t):
            add(
                "unlimited_subcontracting",
                "再委託無制限",
                RiskLevel.HIGH,
                "再委託の事前承諾が不要となっており、業務品質・情報漏洩リスクが高い。",
                action="事前書面承諾制への変更を要求してください。",
            )

        # 不可抗力
        if re.search(r"不可抗力", t):
            add(
                "clear_force_majeure",
                "不可抗力条項あり",
                RiskLevel.LOW,
                "不可抗力条項が確認できました。",
            )

        # 公共工事 / 入札
        if re.search(r"公共工事|入札|発注者", t) and not re.search(r"談合", t):
            add(
                "no_collusion_representation",
                "談合関連表明保証なし",
                RiskLevel.MEDIUM,
                "公共工事と思われますが、談合関連の表明保証が見当たりません。",
            )

        # 業務範囲曖昧
        ambiguous = len(re.findall(r"協議のうえ.{0,5}別途", t))
        if ambiguous >= 3:
            add(
                "ambiguous_scope",
                "業務範囲が曖昧",
                RiskLevel.MEDIUM,
                f"「協議のうえ別途」表現が {ambiguous} 箇所あり、業務範囲が不明確です。",
            )

        # 自動更新
        if re.search(r"自動.{0,3}更新", t) and re.search(r"90 ?日|九十日", t):
            add(
                "auto_renewal_long_optout",
                "自動更新のオプトアウト期間が長い",
                RiskLevel.LOW,
                "自動更新条項のオプトアウト期間が 90 日超です。",
            )

        # If nothing detected — emit an informational issue.
        if not issues:
            add(
                "ambiguous_scope",
                "AI 補助レビューで重大懸念は未検出",
                RiskLevel.LOW,
                "ヒューリスティック検査では明確な追加リスクは検出されませんでした。",
                action="原文と添付資料を必ず人手で確認してください。",
            )

        # Determine overall risk: pick the worst severity present.
        severities = [RiskLevel(i["severity"]) for i in issues]
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        overall = max(severities, key=order.index)

        return {
            "summary": (
                f"[stub] {contract_type} 契約のヒューリスティック AI レビュー結果。"
                f" {len(issues)} 件の論点を検出しました。"
            ),
            "overall_risk": overall.value,
            "issues": issues,
        }

    # ------------------------------------------------------------------
    # Real-mode implementation
    # ------------------------------------------------------------------

    async def _call_claude(
        self, masked_text: str, contract_type: str
    ) -> dict[str, Any]:  # pragma: no cover - exercised in integration tests
        """Invoke the Anthropic SDK with retry."""
        # Lazy import: keep the dependency optional for stub-only environments.
        from anthropic import AsyncAnthropic  # type: ignore[import-not-found]

        client = self._client or AsyncAnthropic(api_key=self._api_key)

        user_prompt = (
            f"以下はマスキング済み契約原文です。契約種別: {contract_type}\n\n"
            f"```\n{masked_text}\n```\n\n"
            "JSON で出力してください。フォーマット: "
            '{"summary": str, "overall_risk": "low|medium|high|critical", '
            '"issues": [{"code": str, "title": str, "severity": '
            '"low|medium|high|critical", "description": str, '
            '"clause_reference": str|null, "recommended_action": str|null}]}'
        )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.5, min=1, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await client.messages.create(
                    model=self._model_id,
                    max_tokens=self._max_tokens,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                    timeout=self._timeout,
                )
                # Best-effort extraction of the text payload.
                blocks = getattr(response, "content", [])
                text = "".join(
                    getattr(b, "text", "") for b in blocks if getattr(b, "type", "") == "text"
                )
                # Recover JSON even when surrounded by prose.
                match = re.search(r"\{.*\}", text, flags=re.DOTALL)
                if not match:
                    raise AIReviewServiceError("Claude response did not contain JSON")
                return cast(dict[str, Any], json.loads(match.group(0)))

        raise AIReviewServiceError("unreachable: AsyncRetrying exited without result")

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------

    def _build_result(
        self,
        *,
        raw: dict[str, Any],
        contract_type: str,
        masked_len: int,
        redactions: int,
        elapsed_ms: int,
    ) -> AIReviewResult:
        issues: list[ReviewIssue] = []
        for entry in raw.get("issues", []):
            try:
                severity = RiskLevel(entry.get("severity", "medium"))
            except ValueError:
                severity = RiskLevel.MEDIUM
            issues.append(
                ReviewIssue(
                    code=str(entry.get("code", "unknown")),
                    title=str(entry.get("title", "")),
                    severity=severity,
                    description=str(entry.get("description", "")),
                    clause_reference=entry.get("clause_reference"),
                    recommended_action=entry.get("recommended_action"),
                    citations=list(entry.get("citations") or []),
                )
            )
        try:
            overall = RiskLevel(raw.get("overall_risk", "medium"))
        except ValueError:
            overall = RiskLevel.MEDIUM
        return AIReviewResult(
            contract_type=contract_type,
            summary=str(raw.get("summary", "")),
            issues=issues,
            overall_risk=overall,
            model_id=self._model_id,
            prompt_template_id=PROMPT_TEMPLATE_ID,
            masked_input_length=masked_len,
            detections_redacted=redactions,
            elapsed_ms=elapsed_ms,
            mode=self._mode,
            generated_at=datetime.now(UTC).isoformat(),
            disclaimer=DISCLAIMER,
        )
