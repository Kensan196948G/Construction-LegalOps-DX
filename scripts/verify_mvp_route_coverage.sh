#!/usr/bin/env bash
#
# verify_mvp_route_coverage.sh — サイドバー全ルートの「右側にデータが出ているか」を機械的に検証する
#
# 目的:
#   frontend/components/layout/sidebar.tsx に定義された全ナビゲーション項目
#   （= サイドバー項目。ハードコードせず毎回ファイルから抽出する）について、
#   実ブラウザ（Playwright / chromium）でそのルートを開き、
#     (1) HTML が 200 であること
#     (2) /_next/static 配下の 404 / 読込失敗が 0 であること
#     (3) 右ペインにデータが実際に描画されていること
#     (4) そのページが呼ぶ API が 200 で、かつ「空」でないこと
#   を判定し、fail-closed（空・判定不能を合格にしない）で exit 1 を返す。
#
# 使い方:
#   scripts/verify_mvp_route_coverage.sh [BASE_URL] [options]
#
#   BASE_URL            既定: https://legalops-mvp.mirai-dx-platform.com
#                       ローカルは http://127.0.0.1:3013 / http://127.0.0.1:8412 など。
#   --timeout SEC       1 ルートあたりのナビゲーション timeout 秒（既定 45、0 以上の整数）
#   --settle MS         描画後の追加待ち時間ミリ秒（既定 2500、0 以上の整数）
#   --json              判定結果を JSON でも出力する
#   --self-test         引数解析と判定ロジックの自己テストをネットワークに出ず実行する
#   --list-routes       抽出したルート一覧を表示して終了する
#   -h | --help         ヘルプ
#
#   `--timeout 30` と `--timeout=30` の両方を受け付ける。値が無い / 数値でない場合は
#   使用方法を stderr に出して exit 64（無限ループしない）。
#
# 環境変数:
#   ALLOW_NON_MVP_HOST=1  許可リスト外のホストを明示的に許可する（既定は拒否 = fail-closed）
#   ROUTE_FILTER=REGEX    ルートを正規表現で絞り込む（部分検証用）
#   PW_ENTRY=<path>       playwright-core のエントリを明示指定
#   PW_BROWSER_CHANNEL=.. chromium 以外のチャネルを使う場合
#
# 終了コード:
#   0  FAIL 0 かつ UNKNOWN 0（N-A は対象外ページとして許容）
#   1  FAIL または UNKNOWN が 1 件以上
#   2  前提条件エラー（本番ホスト指定・依存欠如など）
#   3  自己テスト失敗
#   64 コマンドライン引数の誤り（値の欠落・不正値・未知のオプション）
#
# 厳守事項:
#   - 本番 https://legalops.mirai-dx-platform.com（Cloudflare Access 配下）には絶対に向けない。
#     既定ターゲットは公開 MVP。許可リスト外ホストは既定で拒否する。
#   - 空データ・判定不能を合格にしない。ログイン画面へのリダイレクトも合格にしない。
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SIDEBAR_FILE="${REPO_ROOT}/frontend/components/layout/sidebar.tsx"
DEFAULT_PW_ENTRY="${REPO_ROOT}/frontend/node_modules/playwright-core/index.mjs"
DEFAULT_BASE="https://legalops-mvp.mirai-dx-platform.com"

# 公開 MVP のみ既定許可。本番は明示的に拒否する。
ALLOWED_HOSTS="legalops-mvp.mirai-dx-platform.com localhost 127.0.0.1 ::1"
FORBIDDEN_HOST="legalops.mirai-dx-platform.com"

BASE_URL=""
TIMEOUT_SEC=45
SETTLE_MS=2500
JSON_OUT=0
SELF_TEST=0
LIST_ROUTES=0

# ヘッダのコメントブロック（3 行目以降の連続する '#' 行）をそのまま使用方法として出す。
# 行番号を固定しないので、ヘッダに説明を足しても壊れない。
usage() { awk 'NR > 2 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"; }

# 引数誤りは使用方法を stderr に出して exit 64（無限ループ・暗黙続行を防ぐ）。
usage_error() {
  printf 'ERROR: %s\n\n' "$*" >&2
  usage >&2
  exit 64
}

# 値を 1 つ取るオプションの値検証。値が無い / 空 / 非数を弾く。
need_uint() {
  case "${2:-}" in
    '') usage_error "$1 には値が必要です（例: $1=30）" ;;
    *[!0-9]*) usage_error "$1 には 0 以上の整数が必要です: ${2}" ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --timeout)    need_uint "$1" "${2:-}" ; TIMEOUT_SEC="$2"; shift 2 ;;
    --timeout=*)  need_uint "--timeout" "${1#*=}"; TIMEOUT_SEC="${1#*=}"; shift ;;
    --settle)     need_uint "$1" "${2:-}" ; SETTLE_MS="$2"; shift 2 ;;
    --settle=*)   need_uint "--settle" "${1#*=}"; SETTLE_MS="${1#*=}"; shift ;;
    --json)       JSON_OUT=1; shift ;;
    --self-test)  SELF_TEST=1; shift ;;
    --list-routes) LIST_ROUTES=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    --)           shift; break ;;
    -*)           usage_error "未知のオプションです: $1" ;;
    *)            BASE_URL="$1"; shift ;;
  esac
done

[ -n "$BASE_URL" ] || BASE_URL="$DEFAULT_BASE"
BASE_URL="${BASE_URL%/}"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

# ---------------------------------------------------------------------------
# 1. ターゲットの安全確認（fail-closed）
# ---------------------------------------------------------------------------
HOST="$(printf '%s' "$BASE_URL" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##; s#/.*$##; s#^.*@##; s#:[0-9]+$##')"
[ -n "$HOST" ] || die "BASE_URL からホストを抽出できません: ${BASE_URL}"

if [ "$HOST" = "$FORBIDDEN_HOST" ]; then
  die "本番ホスト (${FORBIDDEN_HOST}) は検証対象外です（Cloudflare Access 配下）。公開 MVP を指定してください。"
fi

host_allowed=0
for h in $ALLOWED_HOSTS; do
  [ "$HOST" = "$h" ] && host_allowed=1 && break
done
if [ "$host_allowed" -ne 1 ] && [ "${ALLOW_NON_MVP_HOST:-0}" != "1" ]; then
  die "許可リスト外のホストです: ${HOST}（許可: ${ALLOWED_HOSTS}）。意図的な場合は ALLOW_NON_MVP_HOST=1 を設定してください。"
fi

# ---------------------------------------------------------------------------
# 2. 依存確認
# ---------------------------------------------------------------------------
PW_ENTRY="${PW_ENTRY:-$DEFAULT_PW_ENTRY}"
command -v node >/dev/null 2>&1 || die "node が見つかりません"
[ -f "$PW_ENTRY" ] || die "playwright-core が見つかりません: ${PW_ENTRY}（PW_ENTRY で指定可能）"

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
[ "$NODE_MAJOR" -ge 18 ] 2>/dev/null || die "node >= 18 が必要です（現在: $(node -v 2>/dev/null))"

# ---------------------------------------------------------------------------
# 3. サイドバーからルート抽出（ハードコードしない）
# ---------------------------------------------------------------------------
extract_routes() {
  [ -f "$SIDEBAR_FILE" ] || die "sidebar.tsx が見つかりません: ${SIDEBAR_FILE}"
  grep -oE "href:[[:space:]]*[\"'][^\"']+[\"']" "$SIDEBAR_FILE" \
    | sed -E "s/^href:[[:space:]]*[\"']//; s/[\"']\$//" \
    | grep -E '^/' \
    | awk '!seen[$0]++'
}

ROUTES="$(extract_routes)"
[ -n "$ROUTES" ] || die "sidebar.tsx から href を 1 件も抽出できませんでした: ${SIDEBAR_FILE}"

if [ -n "${ROUTE_FILTER:-}" ]; then
  ROUTES="$(printf '%s\n' "$ROUTES" | grep -E "$ROUTE_FILTER" || true)"
  [ -n "$ROUTES" ] || die "ROUTE_FILTER='${ROUTE_FILTER}' に一致するルートがありません"
fi

ROUTE_COUNT="$(printf '%s\n' "$ROUTES" | wc -l | tr -d ' ')"

if [ "$LIST_ROUTES" -eq 1 ]; then
  log "sidebar: ${SIDEBAR_FILE}"
  log "routes : ${ROUTE_COUNT}"
  printf '%s\n' "$ROUTES"
  exit 0
fi

# ---------------------------------------------------------------------------
# 4. 実行（判定本体は埋め込み Node スクリプト）
# ---------------------------------------------------------------------------
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/verify-mvp-routes.XXXXXX")"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT INT TERM

ROUTES_FILE="${WORKDIR}/routes.txt"
NODE_SCRIPT="${WORKDIR}/verify.mjs"
printf '%s\n' "$ROUTES" > "$ROUTES_FILE"

cat > "$NODE_SCRIPT" <<'NODE_EOF'
import fs from "node:fs";

/* =========================================================================
 * 判定ロジック（純関数）— network に出ずに self-test から検証できるよう分離
 * ========================================================================= */

const META_KEYS = new Set([
  "page", "page_size", "per_page", "perPage", "size", "limit", "offset",
  "request_id", "requestId", "trace_id", "traceId", "duration_ms",
]);

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

/** { data: ... } エンベロープを剥がす。 */
function unwrapEnvelope(json) {
  if (isObj(json) && "data" in json && (isObj(json.data) || Array.isArray(json.data))) {
    return json.data;
  }
  return json;
}

/** メタキーを除いた数値リーフを収集する。 */
function numericLeaves(v, out = [], depth = 0) {
  if (depth > 8) return out;
  if (typeof v === "number") { if (Number.isFinite(v)) out.push(v); return out; }
  if (Array.isArray(v)) { for (const x of v) numericLeaves(x, out, depth + 1); return out; }
  if (isObj(v)) {
    for (const [k, val] of Object.entries(v)) {
      if (META_KEYS.has(k)) continue;
      numericLeaves(val, out, depth + 1);
    }
  }
  return out;
}

/** 実質的な値を持つスカラーリーフを集める（空文字・ダッシュ・null は除外）。 */
function scalarLeaves(v, out = [], depth = 0) {
  if (depth > 8) return out;
  if (typeof v === "string") { const s = v.trim(); if (s && s !== "-" && s !== "—") out.push(s); return out; }
  if (typeof v === "boolean") { out.push(v); return out; }
  if (Array.isArray(v)) { for (const x of v) scalarLeaves(x, out, depth + 1); return out; }
  if (isObj(v)) { for (const [k, val] of Object.entries(v)) { if (META_KEYS.has(k)) continue; scalarLeaves(val, out, depth + 1); } }
  return out;
}

/**
 * API レスポンス JSON を DATA / EMPTY / UNKNOWN に分類する。
 * fail-closed: 「空だと証明できたら EMPTY」「データがあると証明できたら DATA」、
 * どちらも言えなければ UNKNOWN（合格にはしない）。
 */
export function classifyPayload(json) {
  if (json === null || json === undefined) return { verdict: "UNKNOWN", detail: "レスポンス本文が空/JSON でない" };
  const v = unwrapEnvelope(json);

  if (Array.isArray(v)) {
    return v.length > 0
      ? { verdict: "DATA", detail: `配列 ${v.length} 件` }
      : { verdict: "EMPTY", detail: "配列が空" };
  }
  if (!isObj(v)) return { verdict: "UNKNOWN", detail: `スカラーのみ (${typeof v})` };

  // ページネーション形式 { items: [...] }
  if (Array.isArray(v.items)) {
    return v.items.length > 0
      ? { verdict: "DATA", detail: `items=${v.items.length}` }
      : { verdict: "EMPTY", detail: "items=0" };
  }

  // トップレベルに配列を持つ形（{firms:[...]}, {checks:[...]} 等）
  const arrays = Object.entries(v).filter(([, x]) => Array.isArray(x));
  if (arrays.length > 0) {
    const nonEmpty = arrays.filter(([, x]) => x.length > 0);
    return nonEmpty.length > 0
      ? { verdict: "DATA", detail: `${nonEmpty.map(([k, x]) => `${k}=${x.length}`).join(", ")}` }
      : { verdict: "EMPTY", detail: `${arrays.map(([k]) => `${k}=0`).join(", ")}` };
  }

  // 集計オブジェクト（カウント系）
  const nums = numericLeaves(v);
  const positive = nums.filter((n) => n > 0);
  if (positive.length > 0) {
    return { verdict: "DATA", detail: `0 でないカウント ${positive.length} 件 (max=${Math.max(...positive)})` };
  }
  if (nums.length > 0) {
    return { verdict: "EMPTY", detail: `カウントが全て 0（${nums.length} 項目）` };
  }

  // スカラー設定オブジェクト等
  const scalars = scalarLeaves(v);
  if (scalars.length > 0) {
    return { verdict: "DATA", detail: `スカラーフィールド ${scalars.length} 件` };
  }
  return { verdict: "UNKNOWN", detail: "items / 配列 / カウント / スカラーいずれも無し" };
}

/* --------------------------- DOM 側の判定 --------------------------- */

// 「ありません」系の免責文（法的助言ではありません 等）を空状態と誤判定しないための除外。
const DISCLAIMER_RE = /(ではありません|法的助言|参考情報|確定しません|法的判断|保存されていません)/;
const EMPTY_RE = /(見つかりません|がありません|はありません|登録されていません|されていません|データがありません|選択してください|入力してください|該当なし|0\s*件)/;
const ERROR_RE = /(取得できませんでした|取得に失敗|読み込めませんでした|読み込みに失敗|API 未接続|接続できません|エラーが発生|表示できません|再試行してください|再度お試しください)/;
const COUNT_RE = /(\d[\d,]*)\s*(件|名|社|台|本|個|項目|人|行)/g;

/** 免責文を落とした「意味のある」本文テキストを作る。 */
export function meaningfulText(text) {
  return String(text || "")
    .split(/。|\n|\r/)
    .filter((s) => !DISCLAIMER_RE.test(s))
    .join("\n");
}

function firstMatch(text, re) {
  const m = text.match(re);
  if (!m) return null;
  const i = m.index ?? 0;
  return text.slice(Math.max(0, i - 12), i + m[0].length + 12).replace(/\s+/g, " ").trim();
}

/** DOM から取り出した観測値を評価する。 */
export function classifyDom(dom) {
  const text = meaningfulText(dom.text);
  const countHits = [...text.matchAll(COUNT_RE)]
    .map((m) => Number(m[1].replace(/,/g, "")))
    .filter((n) => Number.isFinite(n) && n >= 1);

  // カード型レイアウト（KPI カード等）は <table> を持たないため、
  // 「数値だけを描画しているリーフ要素」をデータ痕跡として数える。
  // ページネーション/ナビ/操作部品はブラウザ側で除外済み。
  const numLeaves = Number(dom.numLeaves || 0);
  const numLeafSamples = Array.isArray(dom.numLeafSamples) ? dom.numLeafSamples : [];

  const evidence = [];
  if (dom.dataRows >= 1) evidence.push(`表データ行 ${dom.dataRows}`);
  if (dom.articles >= 1) evidence.push(`article ${dom.articles}`);
  if (countHits.length >= 1) evidence.push(`「N 件」表記 ${countHits.length} 個 (max=${Math.max(...countHits)})`);
  if (numLeaves >= 1) {
    evidence.push(`数値表示要素 ${numLeaves} 個（カード/KPI 等。例: ${numLeafSamples.slice(0, 3).join(", ")}）`);
  }

  return {
    errorHit: firstMatch(text, ERROR_RE),
    emptyHit: firstMatch(text, EMPTY_RE),
    countHits,
    numLeaves,
    numLeafSamples,
    cards: Number(dom.cards || 0),
    dataEvidence: evidence,
    hasCollection: dom.dataRows > 0 || dom.rows > 0 || dom.tables > 0 || dom.articles > 0,
    text,
  };
}

/** N-A / UNKNOWN の理由に添える観測値（判定を甘くしないため根拠を残す）。 */
function domContext(sig) {
  const d = sig.dom || {};
  const r = sig.domRaw || {};
  const num = (v) => (v === undefined || v === null ? "-" : v);
  return `table=${num(r.tables)} rows=${num(r.rows)} dataRows=${num(r.dataRows)} `
    + `article=${num(r.articles)} card=${num(d.cards)} numLeaf=${num(d.numLeaves)} textLen=${num(r.textLen)}`;
}

/**
 * 1 ルート分の観測シグナルから PASS / FAIL / UNKNOWN / N-A を決める。
 * 優先順位:
 *   ログインリダイレクト / hard error (HTML/static/API) > エラー表示 >
 *   DOM のデータ実証 > API が空 > API のデータ実証 > 空表示 > N-A > UNKNOWN
 */
export function judgeRoute(sig) {
  const hard = [];
  const redirectNote = sig.redirected
    ? `要求 ${sig.requestedPath ?? "-"} → 最終 ${sig.finalPath ?? "-"}`
    : null;

  // 認証が壊れて全ルートがログインへ飛ぶ状況を「データが無い = N-A」で
  // 見逃さない。リダイレクトの事実を理由に必ず残す。
  if (sig.loginRedirect) {
    hard.push(`ログインへリダイレクト（認証が必要な画面に到達できていない: ${redirectNote}）`);
  }
  if (sig.docStatus !== 200) {
    hard.push(`HTML ${sig.docStatus === 0 ? "取得失敗(status不明)" : sig.docStatus}`);
  }
  if (sig.staticErrors.length > 0) {
    hard.push(`/_next/static エラー ${sig.staticErrors.length} 件 (${sig.staticErrors[0]})`);
  }
  if (sig.apiErrors.length > 0) {
    hard.push(`API エラー ${sig.apiErrors.map((e) => `${e.status} ${e.path}`).join(", ")}`);
  }

  // ログイン以外へのリダイレクトでも事実は出力に残す。
  const note = (!sig.loginRedirect && redirectNote) ? ` [リダイレクト: ${redirectNote}]` : "";

  if (hard.length > 0) return { verdict: "FAIL", detail: hard.join(" / ") + note };

  if (sig.dom.errorHit) return { verdict: "FAIL", detail: `エラー表示: 「${sig.dom.errorHit}」${note}` };

  const pageApis = sig.apiResults.filter((r) => !r.shell);
  const apiData = pageApis.filter((r) => r.classification.verdict === "DATA");
  const apiEmpty = pageApis.filter((r) => r.classification.verdict === "EMPTY");

  if (sig.dom.dataEvidence.length > 0) {
    const detail = [...sig.dom.dataEvidence];
    if (apiData.length > 0) detail.push(`API データ ${apiData.map((e) => `${e.path}(${e.classification.detail})`).join(", ")}`);
    return { verdict: "PASS", detail: detail.join(" / ") + note };
  }

  if (apiEmpty.length > 0) {
    return { verdict: "FAIL", detail: `API が空: ${apiEmpty.map((e) => `${e.path}(${e.classification.detail})`).join(", ")}${note}` };
  }

  if (apiData.length > 0) {
    return { verdict: "PASS", detail: `API データ ${apiData.map((e) => `${e.path}(${e.classification.detail})`).join(", ")}（DOM データ要素なし）${note}` };
  }

  if (sig.dom.emptyHit) return { verdict: "FAIL", detail: `空表示: 「${sig.dom.emptyHit}」${note}` };

  if (pageApis.length === 0 && !sig.dom.hasCollection) {
    return {
      verdict: "N-A",
      detail: `ページ自身の API 呼び出しなし・表/article/カード数値いずれも無し（静的画面または入力待ち画面） [${domContext(sig)}]${note}`,
    };
  }

  return {
    verdict: "UNKNOWN",
    detail: `データ有無の根拠なし (pageAPI=${pageApis.length}`
      + `${pageApis.length > 0 ? `: ${pageApis.map((e) => e.path).join(", ")}` : ""}, ${domContext(sig)})${note}`,
  };
}

/** 集計と exit code。 */
export function summarize(results) {
  const counts = { PASS: 0, FAIL: 0, UNKNOWN: 0, "N-A": 0 };
  for (const r of results) counts[r.verdict] = (counts[r.verdict] || 0) + 1;
  const ok = counts.FAIL === 0 && counts.UNKNOWN === 0;
  return { counts, ok };
}

/* =========================================================================
 * ブラウザ観測
 * ========================================================================= */

const SHELL_API_RE = /^\/api\/v1\/(auth|notifications)(\/|$)/;

/** 1 つの page を観測してルート判定シグナルを返す。 */
export async function runPageCheck(page, url, opts) {
  const api = new Map();
  const staticErrors = [];
  let docStatus = 0;

  const onResponse = (res) => {
    const u = res.url();
    if (u.includes("/api/v1/")) {
      let p;
      try { p = new URL(u); } catch { return; }
      const path = (p.pathname + p.search) || u;
      let entry = api.get(path);
      if (!entry) {
        entry = { path, statuses: [], shell: SHELL_API_RE.test(p.pathname), bodyPromise: null };
        api.set(path, entry);
      }
      entry.statuses.push(res.status());
      if (!entry.bodyPromise && res.status() < 400) {
        entry.bodyPromise = res.json().catch(() => null);
      }
    } else if (u.includes("/_next/static/") && res.status() >= 400) {
      staticErrors.push(`${res.status()} ${u.replace(opts.base, "")}`);
    }
    if (res.request().isNavigationRequest() && res.frame() === page.mainFrame()) {
      docStatus = res.status();
    }
  };
  const onFailed = (req) => {
    const u = req.url();
    if (u.includes("/_next/static/")) staticErrors.push(`FAILED ${u.replace(opts.base, "")}`);
  };

  page.on("response", onResponse);
  page.on("requestfailed", onFailed);

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } catch (e) {
    if (docStatus === 0) {
      try { const r = await page.waitForLoadState("domcontentloaded", { timeout: 5000 }); void r; } catch { /* ignore */ }
    }
  }
  try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch { /* 継続 */ }
  await page.waitForTimeout(opts.settleMs);

  let dom = { text: "", rows: 0, dataRows: 0, tables: 0, listItems: 0, articles: 0, cards: 0, numLeaves: 0, numLeafSamples: [], textLen: 0 };
  let domError = null;
  try {
    dom = await page.evaluate(() => {
      const main = document.querySelector("main") || document.body;
      const text = main.innerText || "";
      const rows = Array.from(main.querySelectorAll("tbody tr"));
      const dataRows = rows.filter((tr) => {
        const cells = Array.from(tr.querySelectorAll("td,th")).map((c) => (c.innerText || "").trim());
        const kept = cells.filter((c) => c && c !== "—" && c !== "-" && c !== "–");
        return kept.length >= 2;
      }).length;

      // カード型レイアウト（KPI カード等）のデータ痕跡:
      // 「数値のみ」を描画しているリーフ要素を数える。操作部品・ナビ・
      // ページネーション・日付/単位付きの数値は除外する。
      const BARE_NUM_RE = /^\d[\d,]*$/;
      const SKIP_TAGS = new Set(["A", "BUTTON", "SELECT", "OPTION", "INPUT", "TEXTAREA", "LABEL", "SCRIPT", "STYLE", "NAV"]);
      const SKIP_CLOSEST = "nav,[role='navigation'],[class*='pagination'],[class*='breadcrumb'],[aria-hidden='true']";
      const numLeafSamples = [];
      let numLeaves = 0;
      for (const el of main.querySelectorAll("*")) {
        if (el.children.length > 0) continue;
        if (SKIP_TAGS.has(el.tagName)) continue;
        if (el.closest(SKIP_CLOSEST)) continue;
        const t = (el.innerText || "").trim();
        if (!BARE_NUM_RE.test(t)) continue;
        const n = Number(t.replace(/,/g, ""));
        if (!Number.isFinite(n) || n < 1) continue;
        numLeaves += 1;
        if (numLeafSamples.length < 3) numLeafSamples.push(t);
      }

      return {
        text: text.slice(0, 30000),
        rows: rows.length,
        dataRows,
        tables: main.querySelectorAll("table").length,
        listItems: main.querySelectorAll("li").length,
        articles: main.querySelectorAll("article").length,
        cards: main.querySelectorAll("[class*='card'],[class*='Card'],[class*='stat'],[class*='kpi'],[class*='metric']").length,
        numLeaves,
        numLeafSamples,
        textLen: text.length,
      };
    });
  } catch (e) {
    domError = String(e && e.message ? e.message : e).split("\n")[0];
  }

  const apiResults = [];
  for (const entry of api.values()) {
    const body = entry.bodyPromise ? await entry.bodyPromise.catch(() => null) : null;
    apiResults.push({
      path: entry.path,
      shell: entry.shell,
      statuses: entry.statuses,
      classification: classifyPayload(body),
    });
  }
  const apiErrors = apiResults
    .filter((e) => e.statuses.some((s) => s >= 400))
    .map((e) => ({ path: e.path, status: Math.max(...e.statuses) }));

  // リダイレクト後の最終 URL を観測する（認証切れで /login に飛ぶ状況を FAIL にする）。
  let finalUrl = "";
  try { finalUrl = page.url(); } catch { /* ignore */ }
  const norm = (u) => {
    try {
      const p = new URL(u);
      // ナビゲーション失敗時は chrome-error:// 等になる。パス扱いせず事実を残す。
      if (p.protocol !== "http:" && p.protocol !== "https:") return `(${p.protocol}//${p.host})`;
      const path = p.pathname.replace(/\/+$/, "") || "/";
      return path + p.search;
    } catch { return String(u); }
  };
  const requestedPath = norm(url);
  const finalPath = finalUrl ? norm(finalUrl) : "";
  const redirected = Boolean(finalPath) && finalPath !== requestedPath;
  const loginRedirect = Boolean(finalPath) && (finalPath === "/login" || finalPath.startsWith("/login/") || finalPath.startsWith("/login?"));

  return {
    docStatus,
    staticErrors,
    apiResults,
    apiErrors,
    dom: classifyDom(dom),
    domRaw: dom,
    domError,
    finalUrl,
    requestedPath,
    finalPath,
    redirected,
    loginRedirect,
  };
}

/* =========================================================================
 * self-test — network に出ずに判定ロジックを検証する（negative verification 含む）
 * ========================================================================= */

async function selfTest(chromium, log) {
  const failures = [];
  const check = (name, cond, extra) => {
    if (cond) log(`  ok   ${name}`);
    else { failures.push(`${name}${extra ? ` — ${extra}` : ""}`); log(`  NG   ${name}${extra ? ` — ${extra}` : ""}`); }
  };

  log("[self-test] 1) payload 分類（空を DATA と誤判定しない）");
  const P = classifyPayload;
  check("items=[] は EMPTY", P({ items: [], total: 0 }).verdict === "EMPTY", P({ items: [], total: 0 }).detail);
  check("items=[1] は DATA", P({ items: [{ id: 1 }], total: 1 }).verdict === "DATA");
  check("envelope {data:{items:[]}} は EMPTY", P({ data: { items: [], total: 0 }, meta: { total: 0 } }).verdict === "EMPTY",
    JSON.stringify(P({ data: { items: [], total: 0 }, meta: { total: 0 } })));
  check("envelope {data:{items:[..]}} は DATA", P({ data: { items: [{ id: 1 }], total: 1 } }).verdict === "DATA");
  check("空配列は EMPTY", P([]).verdict === "EMPTY");
  check("非空配列は DATA", P([{ id: 1 }]).verdict === "DATA");
  check("全カウント 0 は EMPTY", P({ data: { open: 0, closed: 0, total: 0 } }).verdict === "EMPTY",
    JSON.stringify(P({ data: { open: 0, closed: 0, total: 0 } })));
  check("カウント 1 件でも 1 以上なら DATA", P({ data: { open: 0, closed: 3 } }).verdict === "DATA");
  check("メタのみ (page/page_size) は UNKNOWN", P({ data: { page: 1, page_size: 20 } }).verdict === "UNKNOWN",
    JSON.stringify(P({ data: { page: 1, page_size: 20 } })));
  check("空オブジェクトは UNKNOWN", P({ data: {} }).verdict === "UNKNOWN");
  check("null body は UNKNOWN", P(null).verdict === "UNKNOWN");
  check("total=0 のみは EMPTY", P({ data: { total: 0 } }).verdict === "EMPTY", JSON.stringify(P({ data: { total: 0 } })));

  log("[self-test] 2) DOM 判定（空状態テキストをデータと誤認しない）");
  const domEmpty = classifyDom({ text: "案件がありません。「Matter 作成」から登録してください。", dataRows: 0, rows: 1, tables: 1, listItems: 0, articles: 0 });
  check("空状態メッセージを emptyHit として検出", !!domEmpty.emptyHit, JSON.stringify(domEmpty.emptyHit));
  check("空状態に dataEvidence は無い", domEmpty.dataEvidence.length === 0, JSON.stringify(domEmpty.dataEvidence));

  const domData = classifyDom({ text: "契約台帳\nCTR-2026-0001 工事請負契約 ¥3,500,000", dataRows: 20, rows: 20, tables: 1, listItems: 0, articles: 0 });
  check("データ行 20 は dataEvidence あり", domData.dataEvidence.length > 0, JSON.stringify(domData.dataEvidence));

  const domCount = classifyDom({ text: "ひな形一覧 5 件 公開中", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 });
  check("「5 件」をデータ根拠として検出", domCount.dataEvidence.length > 0, JSON.stringify(domCount.dataEvidence));

  const domZero = classifyDom({ text: "登録出願 0 件 登録済 0 件", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 });
  check("「0 件」のみは dataEvidence にならない", domZero.dataEvidence.length === 0, JSON.stringify(domZero.dataEvidence));

  const domDisclaimer = classifyDom({ text: "AI 出力は法的助言ではありません。最終判断は法務担当者が行います。", dataRows: 5, rows: 5, tables: 1, listItems: 0, articles: 0 });
  check("免責文「ではありません」を emptyHit にしない", !domDisclaimer.emptyHit, JSON.stringify(domDisclaimer.emptyHit));

  log("[self-test] 2b) カード型レイアウトのデータ実証（/dashboard 相当）");
  const domKpi = classifyDom({
    text: "レビュー中 8 承認待ちを除く 承認待ち 3 自分宛含む全体 今月完了 0 直近 30 日 高リスク案件 7 未対応のみ",
    dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0, cards: 5,
    numLeaves: 3, numLeafSamples: ["8", "3", "7"],
  });
  check("カードの数値表示をデータ根拠として検出", domKpi.dataEvidence.some((e) => e.includes("数値表示要素")), JSON.stringify(domKpi.dataEvidence));
  check("カード型 KPI ありは PASS", judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: domKpi, domRaw: { tables: 0, rows: 0, dataRows: 0, articles: 0, textLen: 60 },
    requestedPath: "/dashboard", finalPath: "/dashboard", redirected: false, loginRedirect: false,
  }).verdict === "PASS");
  const domKpiZero = classifyDom({
    text: "レビュー中 0 承認待ち 0 高リスク案件 0", dataRows: 0, rows: 0, tables: 0,
    listItems: 0, articles: 0, cards: 3, numLeaves: 0, numLeafSamples: [],
  });
  check("数値が 0 のみのカードはデータ根拠にならない", domKpiZero.dataEvidence.length === 0, JSON.stringify(domKpiZero.dataEvidence));
  check("数値 0 のみのカード画面は PASS にしない", judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: domKpiZero, domRaw: { tables: 0, rows: 0, dataRows: 0, articles: 0, textLen: 30 },
    requestedPath: "/dashboard", finalPath: "/dashboard", redirected: false, loginRedirect: false,
  }).verdict !== "PASS");

  log("[self-test] 2c) ログインリダイレクトを合格扱いにしない");
  const loginSig = judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: classifyDom({ text: "ログイン メールアドレス パスワード", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 }),
    domRaw: { tables: 0, rows: 0, dataRows: 0, articles: 0, textLen: 30 },
    requestedPath: "/contracts", finalPath: "/login", redirected: true, loginRedirect: true,
  });
  check("最終 URL が /login なら FAIL", loginSig.verdict === "FAIL", `${loginSig.verdict}: ${loginSig.detail}`);
  check("リダイレクトの事実（要求→最終）を理由に残す",
    /\/contracts/.test(loginSig.detail) && /\/login/.test(loginSig.detail), loginSig.detail);
  const loginSig2 = judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: classifyDom({ text: "ログイン", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 }),
    domRaw: { tables: 0, rows: 0, dataRows: 0, articles: 0, textLen: 10 },
    requestedPath: "/matters", finalPath: "/login?next=%2Fmatters", redirected: true, loginRedirect: true,
  });
  check("/login?... へのリダイレクトも FAIL", loginSig2.verdict === "FAIL", `${loginSig2.verdict}: ${loginSig2.detail}`);
  const otherRedirect = judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: classifyDom({ text: "ダッシュボード", dataRows: 4, rows: 4, tables: 1, listItems: 0, articles: 0 }),
    domRaw: { tables: 1, rows: 4, dataRows: 4, articles: 0, textLen: 20 },
    requestedPath: "/", finalPath: "/dashboard", redirected: true, loginRedirect: false,
  });
  check("ログイン以外へのリダイレクトは FAIL にしないが事実は残す",
    otherRedirect.verdict === "PASS" && /リダイレクト/.test(otherRedirect.detail), `${otherRedirect.verdict}: ${otherRedirect.detail}`);
  const naSig = judgeRoute({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: classifyDom({ text: "契約検索 全文検索", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 }),
    domRaw: { tables: 0, rows: 0, dataRows: 0, articles: 0, textLen: 12 },
    requestedPath: "/search", finalPath: "/search", redirected: false, loginRedirect: false,
  });
  check("N-A の理由に観測値を含める", naSig.verdict === "N-A" && /table=0/.test(naSig.detail) && /numLeaf=0/.test(naSig.detail), naSig.detail);

  log("[self-test] 3) judgeRoute の優先順位");
  const baseSig = (over = {}) => ({
    docStatus: 200, staticErrors: [], apiErrors: [], apiResults: [],
    dom: classifyDom({ text: "", dataRows: 0, rows: 0, tables: 0, listItems: 0, articles: 0 }),
    ...over,
  });
  check("HTML 500 は FAIL", judgeRoute(baseSig({ docStatus: 500 })).verdict === "FAIL");
  check("static 404 は FAIL", judgeRoute(baseSig({ staticErrors: ["404 /_next/static/x.js"] })).verdict === "FAIL");
  check("API 500 は FAIL", judgeRoute(baseSig({ apiErrors: [{ path: "/contracts", status: 500 }] })).verdict === "FAIL");
  check("データ行ありは PASS", judgeRoute(baseSig({
    dom: classifyDom({ text: "CTR-1 契約", dataRows: 3, rows: 3, tables: 1, listItems: 0, articles: 0 }),
  })).verdict === "PASS");
  check("API が空なら FAIL（データ行なし）", judgeRoute(baseSig({
    apiResults: [{ path: "/matters", shell: false, statuses: [200], classification: { verdict: "EMPTY", detail: "items=0" } }],
  })).verdict === "FAIL");
  check("API 空でもデータ行があれば PASS", judgeRoute(baseSig({
    apiResults: [{ path: "/matters", shell: false, statuses: [200], classification: { verdict: "EMPTY", detail: "items=0" } }],
    dom: classifyDom({ text: "MTR-1 案件", dataRows: 2, rows: 2, tables: 1, listItems: 0, articles: 0 }),
  })).verdict === "PASS");
  check("エラー表示はデータ行より優先して FAIL", judgeRoute(baseSig({
    dom: classifyDom({ text: "一部の指標を取得できませんでした。データ 3 件", dataRows: 3, rows: 3, tables: 1, listItems: 0, articles: 0 }),
  })).verdict === "FAIL");
  check("shell API のみはデータ根拠にならない", judgeRoute(baseSig({
    apiResults: [{ path: "/notifications", shell: true, statuses: [200], classification: { verdict: "DATA", detail: "items=10" } }],
  })).verdict === "N-A");
  check("空表示のみは FAIL", judgeRoute(baseSig({
    dom: classifyDom({ text: "契約が見つかりません", dataRows: 0, rows: 1, tables: 1, listItems: 0, articles: 0 }),
  })).verdict === "FAIL");
  check("根拠なし & 表構造ありは UNKNOWN", judgeRoute(baseSig({
    dom: classifyDom({ text: "フィルタ 対象期間", dataRows: 0, rows: 0, tables: 1, listItems: 0, articles: 0 }),
  })).verdict === "UNKNOWN");

  log("[self-test] 4) 集計と exit code");
  const s1 = summarize([{ verdict: "PASS" }, { verdict: "N-A" }]);
  check("FAIL 0 / UNKNOWN 0 なら ok", s1.ok === true && s1.counts.PASS === 1 && s1.counts["N-A"] === 1);
  check("FAIL があれば not ok", summarize([{ verdict: "PASS" }, { verdict: "FAIL" }]).ok === false);
  check("UNKNOWN があれば not ok", summarize([{ verdict: "UNKNOWN" }]).ok === false);

  log("[self-test] 5) 実ブラウザ + mock 応答での end-to-end（negative verification）");
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  try {
    const mk = async (routeHandler) => {
      const page = await browser.newPage();
      await page.route("**/*", routeHandler);
      return page;
    };
    const html = (body) => `<!doctype html><html lang="ja"><body><main>${body}</main></body></html>`;
    // 「ページが実際に一覧 API を叩く」状況を再現する（クライアントサイド fetch の模擬）。
    // これが無いと API 呼び出しゼロ = N-A になり、判定経路を検証できない。
    const fetchingHtml = (apiPath, body = "") =>
      `<!doctype html><html lang="ja"><body><main>${body}</main><script>fetch("${apiPath}").catch(function(){});</script></body></html>`;

    // (a) API が items:[] を返す → FAIL（空を PASS にしない）
    {
      const page = await mk((route) => {
        const u = route.request().url();
        if (u.includes("/api/v1/contracts")) {
          return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0 }) });
        }
        return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: fetchingHtml("/api/v1/contracts?page=1&page_size=20", "<h1>契約台帳</h1><div id='x'></div>") });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: API items=[] のみ → FAIL", v.verdict === "FAIL", `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (b) API が items:[...] を返す → PASS
    {
      const page = await mk((route) => {
        const u = route.request().url();
        if (u.includes("/api/v1/contracts")) {
          return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: 1 }], total: 1 }) });
        }
        return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: fetchingHtml("/api/v1/contracts?page=1&page_size=20", "<h1>契約台帳</h1>") });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: API items=1 件 → PASS", v.verdict === "PASS", `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (c) HTML が 500 → FAIL
    {
      const page = await mk((route) => route.fulfill({ status: 500, contentType: "text/html; charset=utf-8", body: html("error") }));
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: HTML 500 → FAIL", v.verdict === "FAIL" && /HTML 500/.test(v.detail), `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (d) /_next/static が 404 → FAIL
    {
      const page = await mk((route) => {
        if (route.request().url().includes("/_next/static/")) return route.fulfill({ status: 404, body: "not found" });
        return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html("<h1>ok</h1><script src='/_next/static/chunks/app.js'></script>") });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 500 });
      const v = judgeRoute(sig);
      check("mock: /_next/static 404 → FAIL", v.verdict === "FAIL" && /_next\/static/.test(v.detail), `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (e) API が 500（HTML 200）→ FAIL（甘い判定の禁止）
    {
      const page = await mk((route) => {
        const u = route.request().url();
        if (u.includes("/api/v1/contracts")) return route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ title: "error", status: 500 }) });
        return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: fetchingHtml("/api/v1/contracts?page=1&page_size=20", "<h1>契約台帳</h1>") });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: API 500 + HTML 200 → FAIL", v.verdict === "FAIL" && /API エラー/.test(v.detail), `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (f) 空状態 DOM（データ行なし・空文言あり）→ FAIL
    {
      const page = await mk((route) => route.fulfill({
        status: 200, contentType: "text/html; charset=utf-8",
        body: html("<h1>法務案件</h1><table><tbody><tr><td colspan='5'>案件がありません。「Matter 作成」から登録してください。</td></tr></tbody></table>"),
      }));
      const sig = await runPageCheck(page, "http://mock.local/matters", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: 空状態行のみ → FAIL", v.verdict === "FAIL", `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (g) ログインへリダイレクト → FAIL（N-A にしない）
    // 注: Playwright の route.fulfill は 3xx を実リダイレクトとして追従しないため、
    // ブラウザが最終的に /login に到達する状況をクライアント側遷移で再現する。
    // サーバ側 302/307 の場合は judgeRoute 単体テスト（2c）で検証している。
    {
      const page = await mk((route) => {
        const u = route.request().url();
        if (u.endsWith("/login")) {
          return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html("<h1>ログイン</h1>") });
        }
        return route.fulfill({
          status: 200,
          contentType: "text/html; charset=utf-8",
          body: "<!doctype html><html lang='ja'><body><main>認証を確認しています</main>"
            + "<script>location.replace('/login');</script></body></html>",
        });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 1200 });
      const v = judgeRoute(sig);
      check("mock: /login へリダイレクト → FAIL", v.verdict === "FAIL", `${v.verdict}: ${v.detail}`);
      check("mock: リダイレクト元→先を理由に残す",
        /\/contracts/.test(v.detail) && /\/login/.test(v.detail), v.detail);
      await page.close();
    }

    // (g2) 3xx を fulfill した場合（ブラウザが追従できず到達不能）も FAIL にする
    {
      const page = await mk((route) => {
        const u = route.request().url();
        if (u.endsWith("/login")) {
          return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html("<h1>ログイン</h1>") });
        }
        return route.fulfill({ status: 302, headers: { Location: "/login" }, contentType: "text/html", body: "" });
      });
      const sig = await runPageCheck(page, "http://mock.local/contracts", { base: "http://mock.local", timeoutMs: 10000, settleMs: 500 });
      const v = judgeRoute(sig);
      check("mock: 追従できない 3xx でも FAIL（合格にしない）", v.verdict === "FAIL", `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (h) カード型 KPI 画面 → PASS（表が無くてもデータを実証できる）
    {
      const page = await mk((route) => route.fulfill({
        status: 200, contentType: "text/html; charset=utf-8",
        body: html("<div class='rounded-lg border bg-card'><p>レビュー中</p><p class='mt-2 text-3xl font-bold'>8</p></div>"
          + "<div class='rounded-lg border bg-card'><p>承認待ち</p><p class='mt-2 text-3xl font-bold'>3</p></div>"
          + "<div class='rounded-lg border bg-card'><p>今月完了</p><p class='mt-2 text-3xl font-bold'>0</p></div>"),
      }));
      const sig = await runPageCheck(page, "http://mock.local/dashboard", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: カード型 KPI 画面 → PASS", v.verdict === "PASS", `${v.verdict}: ${v.detail}`);
      await page.close();
    }

    // (i) 全部 0 のカード + ページネーションの数字だけ → PASS にしない
    {
      const page = await mk((route) => route.fulfill({
        status: 200, contentType: "text/html; charset=utf-8",
        body: html("<div class='rounded-lg border bg-card'><p>登録出願</p><p class='mt-2 text-3xl font-bold'>0</p></div>"
          + "<nav aria-label='ページ'><a href='?page=1'>1</a><a href='?page=2'>2</a><a href='?page=3'>3</a></nav>"
          + "<select><option>2</option></select>"),
      }));
      const sig = await runPageCheck(page, "http://mock.local/ip-assets", { base: "http://mock.local", timeoutMs: 10000, settleMs: 300 });
      const v = judgeRoute(sig);
      check("mock: 0 のカード + ナビ/選択肢の数字はデータ根拠にしない", v.verdict !== "PASS", `${v.verdict}: ${v.detail}`);
      await page.close();
    }
  } finally {
    await browser.close();
  }

  log("");
  if (failures.length === 0) { log("[self-test] ALL PASS"); return 0; }
  log(`[self-test] FAILED ${failures.length} 件:`);
  for (const f of failures) log(`  - ${f}`);
  return 3;
}

/* =========================================================================
 * main
 * ========================================================================= */

function fmt(verdict) { return verdict.padEnd(7); }

async function main() {
  const args = process.argv.slice(2);
  const opt = { base: "", routesFile: "", timeoutMs: 45000, settleMs: 2500, json: false, selfTest: false };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--self-test") opt.selfTest = true;
    else if (a === "--json") opt.json = true;
    else if (a === "--base") opt.base = args[++i];
    else if (a === "--routes") opt.routesFile = args[++i];
    else if (a === "--timeout") opt.timeoutMs = Number(args[++i]) * 1000;
    else if (a === "--settle") opt.settleMs = Number(args[++i]);
  }

  const { chromium } = await import(process.env.PW_ENTRY);

  if (opt.selfTest) {
    const code = await selfTest(chromium, (m) => console.log(m));
    process.exit(code);
  }

  const routes = fs.readFileSync(opt.routesFile, "utf8").split("\n").map((s) => s.trim()).filter(Boolean);
  const browser = await chromium.launch({ args: ["--no-sandbox"], channel: process.env.PW_BROWSER_CHANNEL || undefined });

  console.log(`target : ${opt.base}`);
  console.log(`routes : ${routes.length}`);
  console.log(`engine : chromium (playwright-core)`);
  console.log("");

  const results = [];
  try {
    for (const route of routes) {
      const page = await browser.newPage();
      const url = opt.base + route;
      let res;
      try {
        const sig = await runPageCheck(page, url, { base: opt.base, timeoutMs: opt.timeoutMs, settleMs: opt.settleMs });
        const v = judgeRoute(sig);
        res = { route, url, verdict: v.verdict, detail: v.detail, domError: sig.domError, domRaw: sig.domRaw, apiResults: sig.apiResults };
      } catch (e) {
        res = { route, url, verdict: "UNKNOWN", detail: `検証中に例外: ${String(e && e.message ? e.message : e).split("\n")[0]}` };
      }
      results.push(res);
      console.log(`${fmt(res.verdict)} ${res.route.padEnd(24)} ${res.detail}`);
      if (res.domError) console.log(`        (DOM 取得エラー: ${res.domError})`);
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const { counts, ok } = summarize(results);
  console.log("");
  console.log("---- summary ----");
  console.log(`total=${results.length} PASS=${counts.PASS} FAIL=${counts.FAIL} UNKNOWN=${counts.UNKNOWN} N-A=${counts["N-A"]}`);

  const failed = results.filter((r) => r.verdict === "FAIL");
  const unknown = results.filter((r) => r.verdict === "UNKNOWN");
  const na = results.filter((r) => r.verdict === "N-A");
  if (failed.length > 0) {
    console.log("");
    console.log(`FAIL (${failed.length}):`);
    for (const r of failed) console.log(`  - ${r.route}: ${r.detail}`);
  }
  if (unknown.length > 0) {
    console.log("");
    console.log(`UNKNOWN (${unknown.length}):`);
    for (const r of unknown) console.log(`  - ${r.route}: ${r.detail}`);
  }
  if (na.length > 0) {
    console.log("");
    console.log(`N-A (${na.length}) ※ API 呼び出しもデータ構造も無い静的画面として対象外:`);
    for (const r of na) console.log(`  - ${r.route}: ${r.detail}`);
  }

  if (opt.json) {
    console.log("");
    console.log(JSON.stringify({ target: opt.base, counts, ok, results }, null, 2));
  }

  console.log("");
  console.log(ok ? "RESULT: OK (FAIL 0 / UNKNOWN 0)" : "RESULT: NG (fail-closed)");
  process.exit(ok ? 0 : 1);
}

main().catch((e) => {
  console.error(`FATAL: ${e && e.stack ? e.stack : e}`);
  process.exit(2);
});
NODE_EOF

log "== verify_mvp_route_coverage =="
log "target : ${BASE_URL}"
log "sidebar: ${SIDEBAR_FILE}"
log "routes : ${ROUTE_COUNT} 件（sidebar.tsx から抽出）"
log "node   : $(node -v)"
log ""

NODE_ARGS=(--base "$BASE_URL" --timeout "$TIMEOUT_SEC" --settle "$SETTLE_MS")
[ "$JSON_OUT" -eq 1 ] && NODE_ARGS+=(--json)

# 引数解析の自己テスト。値欠落で無限ループしないこと・不正値を弾くことを
# 実際に自分自身を再帰起動して exit code で確認する。
arg_self_test() {
  local failures=0 out code
  run_case() {
    local name="$1" exp="$2"; shift 2
    out="$("$0" "$@" 2>&1)"; code=$?
    if [ "$code" -eq "$exp" ]; then
      printf '  ok   %s (exit %s)\n' "$name" "$code"
    else
      printf '  NG   %s: exit %s (expected %s)\n' "$name" "$code" "$exp"
      failures=$((failures + 1))
    fi
  }
  log "[self-test] 0) 引数解析（値欠落・不正値は exit 64、無限ループしない）"
  run_case "--timeout 単独（値なし）" 64 "$BASE_URL" --timeout
  run_case "--settle 単独（値なし）" 64 "$BASE_URL" --settle
  run_case "--timeout 30 形式" 0 "$BASE_URL" --timeout 30 --list-routes
  run_case "--timeout=30 形式" 0 "$BASE_URL" --timeout=30 --list-routes
  run_case "--settle=100 形式" 0 "$BASE_URL" --settle=100 --list-routes
  run_case "--timeout= （空値）" 64 "$BASE_URL" --timeout=
  run_case "--timeout abc（不正値）" 64 "$BASE_URL" --timeout abc --list-routes
  run_case "--timeout=abc（不正値）" 64 "$BASE_URL" --timeout=abc
  run_case "--settle -1（負値）" 64 "$BASE_URL" --settle -1
  run_case "未知のオプション" 64 "$BASE_URL" --bogus
  run_case "--help" 0 --help
  return "$failures"
}

if [ "$SELF_TEST" -eq 1 ]; then
  arg_failures=0
  arg_self_test || arg_failures=$?
  log ""
  PW_ENTRY="$PW_ENTRY" node "$NODE_SCRIPT" --self-test
  node_rc=$?
  if [ "$arg_failures" -ne 0 ] || [ "$node_rc" -ne 0 ]; then
    log ""
    log "[self-test] FAILED（引数解析: ${arg_failures} 件 / 判定ロジック: exit ${node_rc}）"
    exit 3
  fi
  exit 0
fi

NODE_ARGS+=(--routes "$ROUTES_FILE")

PW_ENTRY="$PW_ENTRY" node "$NODE_SCRIPT" "${NODE_ARGS[@]}"
exit $?
