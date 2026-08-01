/**
 * access_token のリフレッシュ実装 (Edge ランタイム互換)。
 *
 * 設計方針:
 *   - HENNGE One / Entra ID の OIDC `token_endpoint` を直接叩くのではなく、
 *     backend `/api/v1/auth/refresh` に委譲する。これにより
 *     `client_secret` (Confidential Client) がブラウザ側コードバンドルに
 *     入らないこと、また backend 側で **fail-closed** な検証 (issuer/aud/
 *     tenant 制限) を一括できることを保証する。
 *   - `fetch` のみを使用し Node 固有 API を import しない (Edge OK)。
 *   - 失敗時は **必ず** `null` を返す。例外を握り潰さず呼び出し側で
 *     `RefreshAccessTokenError` を立てる前提。
 *   - タイムアウトは 5 秒で打ち切り (worker を塞がない)。
 *
 * backend 側 `/api/v1/auth/refresh` の I/O 仕様:
 *   request : `{ "refresh_token": string }`
 *   response: `{ "access_token": string, "id_token"?: string,
 *               "refresh_token"?: string, "expires_in": number }`
 *   error   : RFC 7807 problem+json
 */

export interface RefreshedTokens {
  /** 新しい access_token (Bearer)。空文字は許容しない。 */
  access_token: string;
  /** IdP がローテーションした場合のみ存在する。 */
  id_token?: string;
  /**
   * refresh_token rotation を採用しているため、レスポンスに含まれる場合は
   * 新しい値で置き換える。
   */
  refresh_token?: string;
  /** UNIX epoch 秒 (絶対時刻)。`expires_in` をクライアント時計で換算して保持。 */
  expires_at: number;
}

const REFRESH_TIMEOUT_MS = 15_000;

/**
 * backend に refresh_token を渡して新しい access_token を取得する。
 *
 * @returns 成功時は {@link RefreshedTokens}、失敗時は `null`。
 *          呼び出し側 (auth.config の jwt callback) で
 *          `token.error = "RefreshAccessTokenError"` を立て、
 *          UI 側で再ログイン誘導 (signIn 再実行) を行うこと。
 */
export async function refreshAccessToken(
  refreshToken: string,
): Promise<RefreshedTokens | null> {
  if (!refreshToken) return null;

  const baseUrl =
    process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      // fail-closed: 401 / 403 / 5xx いずれも再ログイン誘導に倒す。
      return null;
    }

    const payload = (await res.json()) as {
      access_token?: unknown;
      id_token?: unknown;
      refresh_token?: unknown;
      expires_in?: unknown;
    };

    if (typeof payload.access_token !== "string" || payload.access_token.length === 0) {
      return null;
    }

    // `expires_in` は OIDC 標準で秒数 (number)。欠落時は 15 分を仮置きする。
    const expiresInSec =
      typeof payload.expires_in === "number" && payload.expires_in > 0
        ? payload.expires_in
        : 60 * 15;

    return {
      access_token: payload.access_token,
      id_token: typeof payload.id_token === "string" ? payload.id_token : undefined,
      refresh_token:
        typeof payload.refresh_token === "string" ? payload.refresh_token : undefined,
      expires_at: Math.floor(Date.now() / 1000) + expiresInSec,
    };
  } catch {
    // ネットワーク / abort / parse 等いずれも null に倒す (fail-closed)
    return null;
  } finally {
    clearTimeout(timer);
  }
}
