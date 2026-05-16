/**
 * Server-side session bridge (Server Components / Route Handlers only)
 * =====================================================================
 *
 * Server Component / Route Handler から呼ぶ初期化。
 * Client Component では `@/lib/auth/session-bridge` (client module) を使うこと。
 *
 * このファイルは `auth.ts` / `auth.config.ts` を import するため、
 * **Edge ランタイム非互換**。`middleware.ts` からは絶対に import しないこと。
 */

import {
  setAuthTokenProvider,
  type AuthTokenProvider,
} from "@/lib/api/client";

/**
 * Server Component / Server Action / Route Handler から呼ぶ初期化。
 *
 * `auth()` を **lazy 動的 import** することで、本ファイルがクライアント
 * バンドルに引きずられても next-auth Node 専用 API が読み込まれないようにする。
 *
 * @returns 後始末関数。`finally` で必ず呼んで provider をクリアする。
 */
export async function bindServerSession(): Promise<() => void> {
  let token: string | null | undefined;
  try {
    const mod: unknown = await import("@/auth").catch(() => null);
    if (mod && typeof mod === "object" && "auth" in mod) {
      const authFn = (mod as { auth?: () => Promise<unknown> }).auth;
      if (typeof authFn === "function") {
        const session = (await authFn()) as
          | { user?: { accessToken?: string } }
          | null
          | undefined;
        token = session?.user?.accessToken;
      }
    }
  } catch {
    token = null;
  }

  const provider: AuthTokenProvider = async () => token ?? null;
  setAuthTokenProvider(provider);

  return () => {
    setAuthTokenProvider(null);
  };
}
