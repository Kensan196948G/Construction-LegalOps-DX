import { http, HttpResponse } from "msw";

/**
 * MSW handlers (Backend `/api/v1/*` の最小フィクスチャ)。
 *
 * 各 Feature Team はこのファイルにハンドラを追加せず、テストごとに
 * `server.use(...)` で個別 override すること。ここはあくまで「全テストに
 * 共通する既定値」だけを置く。
 *
 * Backend が確定するまで、認証関連の最小レスポンスのみ提供する。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const handlers = [
  /**
   * GET /api/v1/auth/me
   * - フロントの hook が現在ユーザ情報を取得するために呼ぶ想定
   * - 既定では未認証 (401) を返す。認証済みケースは各テストで上書き
   */
  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json(
      {
        error: "unauthenticated",
        message: "認証情報がありません。",
      },
      { status: 401 },
    );
  }),

  /**
   * POST /api/v1/auth/logout
   * - 成功時 204
   */
  http.post(`${API_BASE}/auth/logout`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  /**
   * GET /api/v1/health
   * - Dockerfile HEALTHCHECK や Page Team が叩く `/api/health` を兼ねる
   *   (フロント側 Route Handler が backend にプロキシする想定)
   */
  http.get(`${API_BASE}/health`, () => {
    return HttpResponse.json({ status: "ok" });
  }),
];
