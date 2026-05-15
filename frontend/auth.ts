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
 * NOTE: ここでは Edge 非互換な追加 Provider やアダプタを足す余地を残しているが、
 *       現状は `auth.config` をそのまま流用する。Loop 4 で Prisma アダプタ等を
 *       追加する場合はこのファイルにだけ書く (middleware は edge-safe 維持)。
 */
export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
