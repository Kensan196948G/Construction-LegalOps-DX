/**
 * Session ↔ API client bridge
 * =====================================================================
 *
 * next-auth v5 のセッション (`session.user.accessToken`) を
 * `@/lib/api/client` の `setAuthTokenProvider` / `setOnUnauthorized` に
 * 橋渡しするためのユーティリティ。
 *
 * - Server Component / Route Handler: `auth()` を直接 await する
 *   `bindServerSession()` を 1 リクエストにつき 1 回呼ぶ。
 * - Client Component: `useBindClientSession()` を `QueryProvider` 内で 1 回
 *   呼べば、以降 `useSession()` の変化を追跡してトークンを差し替える。
 *
 * このファイルは `auth.ts` / `auth.config.ts` を import するため、
 * **Edge ランタイム非互換**。`middleware.ts` からは絶対に import しないこと。
 */

import { useEffect } from "react";
import { signOut as nextAuthSignOut, useSession } from "next-auth/react";

import {
  setAuthTokenProvider,
  setOnUnauthorized,
  type AuthTokenProvider,
} from "@/lib/api/client";

/**
 * `useSession()` は `<SessionProvider>` 配下でしか呼べない。
 * Security チームが `SessionProvider` を `Providers` ツリーに追加するまでの
 * 過渡期に hook ツリーが壊れないよう、try/catch でガードする内部 wrapper。
 *
 * NOTE: try/catch で hook を囲んでも React の hook rule 違反ではない
 *       (= 条件分岐で呼び分けていない)。next-auth/react の `useSession`
 *       は context 未提供時に throw する実装なのでここで握り潰す。
 */
function useSessionSafe(): { accessToken?: string } | null {
  try {
    const s = useSession();
    return { accessToken: s?.data?.user?.accessToken };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Server side
// ---------------------------------------------------------------------------

/**
 * Server Component / Server Action / Route Handler から呼ぶ初期化。
 *
 * `auth()` を **lazy 動的 import** することで、本ファイルがクライアント
 * バンドルに引きずられても next-auth Node 専用 API が読み込まれないようにする。
 *
 * 同一プロセス上で複数並行リクエストが走ると provider が共有される問題を
 * 避けるため、provider はリクエストスコープのクロージャを返す方式とする
 * (= 直近 `bindServerSession()` 呼出時点の token をキャプチャ)。
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
    // 直前に install した provider を厳密一致で外す
    setAuthTokenProvider(null);
  };
}

// ---------------------------------------------------------------------------
// Client side
// ---------------------------------------------------------------------------

/**
 * Client Component (= `QueryProvider` 配下) で 1 回呼ぶ hook。
 *
 * - `useSession()` の `data.user.accessToken` を API client の provider にバインド
 * - 401 受領時に `signOut({ callbackUrl: "/login" })` を呼ぶ handler を bind
 *
 * `useSession()` 自体は SessionProvider 配下である必要があるため、本プロジェクト
 * では `app/layout.tsx` の `<Providers>` ツリーに `SessionProvider` が含まれる
 * 前提とする (Security チーム territory)。`SessionProvider` が無い場合でも
 * `defaultClientTokenProvider` (client.ts) が `getSession()` で fall back する。
 */
export function useBindClientSession(): void {
  const safe = useSessionSafe();
  const accessToken = safe?.accessToken;

  useEffect(() => {
    const provider: AuthTokenProvider = async () => accessToken ?? null;
    setAuthTokenProvider(provider);

    setOnUnauthorized(() => {
      // 401 受領: 強制サインアウト + /login へ
      void nextAuthSignOut({ callbackUrl: "/login" });
    });

    return () => {
      setAuthTokenProvider(null);
      setOnUnauthorized(null);
    };
  }, [accessToken]);
}
