import NextAuth from "next-auth";

import { authConfig } from "./auth.config";

/**
 * next-auth v5 (beta) ルートエクスポート。
 *
 * - `handlers`  : `app/api/auth/[...nextauth]/route.ts` から再エクスポート (Pages Team 担当)
 * - `auth`      : Server Component / Route Handler / Server Action 内でセッション取得
 * - `signIn`    : Server Action 経由のサインイン (`<form action={signIn}>` 形式)
 * - `signOut`   : 同上
 *
 * Loop 4 (Security 統合) ノート:
 *   - 本ファイルは Node ランタイム前提。Edge 限定 (middleware) からは
 *     `auth.config.ts` を直接読むこと。
 *   - Prisma / DB adapter / Node-only Provider を追加する場合はここに記述する
 *     (middleware には伝播させない)。
 *   - access_token のリフレッシュは `auth.config.ts` の `jwt` callback 内で
 *     `lib/auth/refresh-token` に委譲済み。バックエンドで refresh_token が
 *     失効した場合は `session.error === "RefreshAccessTokenError"` が立つ。
 */
export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
