import { http, HttpResponse } from "msw";

/**
 * MSW handlers (Backend `/api/v1/*` の最小フィクスチャ)。
 *
 * 各 Feature Team はこのファイルにハンドラを追加せず、テストごとに
 * `server.use(...)` で個別 override すること。ここはあくまで「全テストに
 * 共通する既定値」だけを置く。
 *
 * フィクスチャは `frontend/lib/api/schemas.ts` の zod schema が
 * `safeParse` で通る形に整形している。Backend `docs/api_design.md` の
 * `{ data, meta }` エンベロープ規約に準拠。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** `meta.request_id` 用ダミー (RFC4122 v4 風) */
function reqId(): string {
  return "00000000-0000-4000-8000-000000000001";
}

export const handlers = [
  // ===========================================================================
  // Health / Meta
  // ===========================================================================

  /**
   * GET /api/v1/healthz
   */
  http.get(`${API_BASE}/healthz`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  /**
   * GET /api/v1/readyz
   */
  http.get(`${API_BASE}/readyz`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  /**
   * GET /api/v1/health  (legacy / pages 用)
   */
  http.get(`${API_BASE}/health`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  /**
   * GET /api/v1/version
   */
  http.get(`${API_BASE}/version`, () => {
    return HttpResponse.json({ version: "0.1.0-test", commit: "deadbeef" });
  }),

  // ===========================================================================
  // Auth
  // ===========================================================================

  /**
   * GET /api/v1/auth/me
   * - 既定では未認証 (401 + RFC7807) を返す。
   * - 認証済みケースは各テストで `server.use(http.get(..., () => json({data: user})))` 上書き。
   */
  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json(
      {
        type: "about:blank",
        title: "Unauthenticated",
        status: 401,
        detail: "認証情報がありません。",
        request_id: reqId(),
      },
      { status: 401, headers: { "Content-Type": "application/problem+json" } },
    );
  }),

  /**
   * POST /api/v1/auth/sso/logout
   */
  http.post(`${API_BASE}/auth/sso/logout`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ===========================================================================
  // Dashboard — 既定の "空" レスポンス (Test 側で上書き可)
  // ===========================================================================

  /**
   * GET /api/v1/dashboard/kpis
   * - `apiResponse(dashboardKpisSchema)` 互換: `{ data: { ... }, meta }`
   */
  http.get(`${API_BASE}/dashboard/kpis`, () => {
    return HttpResponse.json({
      data: {
        total_contracts: 0,
        in_review: 0,
        pending_approval: 0,
        high_risk_open: 0,
        reviews_this_month: 0,
        avg_review_minutes: 0,
      },
      meta: { request_id: reqId() },
    });
  }),

  /**
   * GET /api/v1/dashboard/timeseries
   */
  http.get(`${API_BASE}/dashboard/timeseries`, ({ request }) => {
    const url = new URL(request.url);
    const metric = url.searchParams.get("metric") ?? "contracts_created";
    return HttpResponse.json({
      data: {
        metric,
        points: [],
      },
      meta: { request_id: reqId() },
    });
  }),

  // ===========================================================================
  // Contracts / Reviews / Risks — 空ページの既定値
  // ===========================================================================

  /**
   * GET /api/v1/contracts
   * - `paginatedSchema(contractSchema)` 互換: `{ data: [], meta: { page, page_size, total } }`
   */
  http.get(`${API_BASE}/contracts`, () => {
    return HttpResponse.json({
      data: [],
      meta: { page: 1, page_size: 20, total: 0, request_id: reqId() },
    });
  }),

  /**
   * GET /api/v1/reviews
   */
  http.get(`${API_BASE}/reviews`, () => {
    return HttpResponse.json({
      data: [],
      meta: { page: 1, page_size: 20, total: 0, request_id: reqId() },
    });
  }),

  /**
   * GET /api/v1/risks
   */
  http.get(`${API_BASE}/risks`, () => {
    return HttpResponse.json({
      data: [],
      meta: { page: 1, page_size: 20, total: 0, request_id: reqId() },
    });
  }),

  /**
   * GET /api/v1/notifications
   */
  http.get(`${API_BASE}/notifications`, () => {
    return HttpResponse.json({
      data: [],
      meta: { page: 1, page_size: 20, total: 0, request_id: reqId() },
    });
  }),
];
