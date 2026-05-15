import type { NextAuthConfig } from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";

/**
 * next-auth v5 (beta) shared configuration.
 *
 * このファイルは Edge ランタイム互換であることが要件のため、Node 専用 API
 * (Prisma などの DB アダプタ、`bcrypt`、Node `fs` 等) を **絶対に import しない**こと。
 * 重い処理を伴う Provider は `auth.ts` 側でだけ追加する。
 *
 * 現状は Microsoft Entra ID (HENNGE One 経由 OIDC) の雛形のみ。
 * Loop 4 にて HENNGE One discovery URL を反映し、`issuer` を実値に切り替える。
 */
export const authConfig = {
  // セッションは JWT (Edge ランタイムでも検証可能)
  session: {
    strategy: "jwt",
    // 営業日 1 日 (8 時間) を上限とする。リフレッシュは Loop 4 で実装。
    maxAge: 60 * 60 * 8,
  },

  // 認証関連ページは App Router の `/login` を使用 (Pages Team 提供)
  pages: {
    signIn: "/login",
    error: "/login",
  },

  providers: [
    // -------------------------------------------------------------------------
    // Microsoft Entra ID via HENNGE One (OIDC)
    //
    // HENNGE One が ID プロバイダプロキシとなるため、最終的な `issuer` は
    // HENNGE 側の discovery URL から取得した issuer 値を設定する必要がある。
    //
    // TODO(Loop 4):
    //   - `HENNGE_OIDC_DISCOVERY_URL` から well-known を取得して issuer を導出
    //   - `id_token_hint` / `prompt=login` 等の HENNGE 要件パラメータを反映
    //   - PKCE / state 検証は next-auth 既定実装でカバーされるが、tenant 制限を
    //     `profile` callback で再確認すること (テナント外ユーザーの拒否)
    // -------------------------------------------------------------------------
    MicrosoftEntraID({
      clientId: process.env.AUTH_MICROSOFT_ENTRA_ID_ID,
      clientSecret: process.env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
      issuer: process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
      // next-auth v5: OIDC scopes
      authorization: { params: { scope: "openid profile email offline_access" } },
    }),
  ],

  callbacks: {
    /**
     * ルート保護 (Edge middleware から呼ばれる)。
     * - `/login` は誰でも閲覧可
     * - それ以外は認証済みユーザーのみ
     * - `/api`, `_next/*`, `favicon.ico` は middleware matcher で除外済み
     */
    authorized({ auth, request }) {
      const { nextUrl } = request;
      const isLoggedIn = Boolean(auth?.user);
      const isOnLogin = nextUrl.pathname.startsWith("/login");

      if (isOnLogin) {
        // 既にログイン済みなら `/` (App Router 内で `/dashboard` 等へ Redirect 想定) へ
        if (isLoggedIn) {
          return Response.redirect(new URL("/", nextUrl));
        }
        return true;
      }

      return isLoggedIn;
    },

    /**
     * JWT 生成 / 更新。
     * - 初回サインイン時 (`account` あり) にトークン群を保存
     * - 以降のリクエストでは保持した値を返す
     * - role / department_id は backend `/api/v1/auth/me` から取り出す想定だが、
     *   雛形では Entra ID profile に含まれる値を仮置き (Loop 4 で差し替え)
     */
    async jwt({ token, account, profile, user }) {
      if (account) {
        token.id_token = account.id_token;
        token.access_token = account.access_token;
        token.expires_at = account.expires_at;
      }

      if (profile) {
        // TODO(Loop 4): backend `/api/v1/auth/me` を呼んで role/department_id を解決する
        const p = profile as Record<string, unknown>;
        token.role = (p.role as string | undefined) ?? token.role ?? "viewer";
        token.department_id =
          (p.department_id as string | undefined) ?? token.department_id ?? null;
      }

      if (user?.id && !token.sub) {
        token.sub = user.id;
      }

      return token;
    },

    /**
     * クライアントに公開する Session の整形。
     * `next-auth.d.ts` の module augmentation と整合させること。
     */
    async session({ session, token }) {
      if (session.user) {
        session.user.id = (token.sub as string | undefined) ?? session.user.id;
        session.user.role = (token.role as string | undefined) ?? "viewer";
        session.user.departmentId =
          (token.department_id as string | null | undefined) ?? null;
        session.user.accessToken = token.access_token as string | undefined;
      }
      return session;
    },
  },

  // CSRF / cookie 設定は next-auth 既定に従う。
  // Loop 4 で SameSite=strict + Secure を本番要件として明示する。
  trustHost: true,
} satisfies NextAuthConfig;
