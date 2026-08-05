import NextAuth from "next-auth";

import { authConfig } from "./auth.config";

/**
 * Edge runtime middleware。
 *
 * `authConfig` のみを使って `NextAuth` を初期化することで、middleware が
 * Edge ランタイム互換のまま動作する (DB アダプタ等 Node-only コードを含めない)。
 *
 * matcher は以下を**除外**する:
 *   - `/api/*`           : Route Handlers (next-auth handlers 含む) と AI 免責の例外経路
 *   - `/_next/static/*`  : 静的アセット
 *   - `/_next/image/*`   : next/image 最適化エンドポイント
 *   - `favicon.ico`      : ファビコン
 *   - `/login`           : 未認証アクセスのランディング
 *
 * 上記以外は `authConfig.callbacks.authorized` で保護される。
 */
export const { auth: middleware } = NextAuth(authConfig);

export default middleware;

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|favicon\\.svg|logo\\.svg|login).*)"],
};
