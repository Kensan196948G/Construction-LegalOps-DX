/**
 * Client-side session bridge (Client Components only)
 * =====================================================================
 *
 * Client Component 用セッション↔API client ブリッジ。
 * Server Component / Route Handler では `@/lib/auth/session-bridge.server` を使うこと。
 *
 * `useBindClientSession()` を `QueryProvider` 内で 1 回呼べば、
 * 以降 `useSession()` の変化を追跡してトークンを差し替える。
 */
"use client";

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
