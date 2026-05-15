/**
 * API client initialization
 * =====================================================================
 *
 * `QueryProvider` 内 (Client Component) から 1 回だけ呼ぶ初期化処理。
 *
 * - next-auth `useSession()` → `setAuthTokenProvider()` の橋渡し
 * - 401 ハンドラのバインド
 *
 * 副作用 import 禁止: 必ず明示的に `useInitApiClient()` を呼ぶこと。
 *
 * Server 側の初期化は `@/lib/auth/session-bridge#bindServerSession` を
 * Server Component の冒頭で `await` する。
 */

"use client";

import { useBindClientSession } from "@/lib/auth/session-bridge";

/**
 * Client-side で API client を session に bind する hook。
 * `QueryProvider` の中で 1 回呼べばよい。
 *
 * 戻り値は無い (React の effect で provider を install する)。
 */
export function useInitApiClient(): void {
  useBindClientSession();
}
