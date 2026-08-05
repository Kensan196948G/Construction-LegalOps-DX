import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";

import { refreshAccessToken } from "@/lib/auth/refresh-token";

/**
 * next-auth v5 (beta) 共有設定 — HENNGE One 経由 Entra ID OIDC 統合 (Loop 4)
 *
 * ## Edge ランタイム互換性
 * このファイルは middleware から import されるため、Node 専用 API
 * (DB アダプタ、`bcrypt`、Node `fs` 等) を **絶対に import してはならない**。
 * Node-only な処理は `auth.ts` 側に置くこと。
 * `lib/auth/refresh-token` は意図的に `fetch` のみ使用しており Edge 互換である。
 *
 * ## 認証フロー
 *
 * 1. ユーザーが `/login` の "サインイン" を押すと `signIn("microsoft-entra-id")`
 *    が発火、`authorization_endpoint` (HENNGE 経由) へリダイレクト。
 *    `scope=openid profile email offline_access` で `refresh_token` を取得する。
 * 2. コールバックで `account` が `jwt` callback に渡る。ここで:
 *    - `id_token / access_token / refresh_token / expires_at` を JWT に保存
 *    - backend `/api/v1/auth/me` を **必ず** 叩いて `role / department_id` を解決
 *    - backend の解決に失敗した場合は `token.error = "BackendUnauthorized"` を立て、
 *      session callback 側でクライアントが再ログインを要求できるようにする
 * 3. 以降のリクエストでは access_token が期限切れになると `refreshAccessToken`
 *    を呼んで backend `/api/v1/auth/refresh` に refresh_token を委譲する。
 *
 * ## RBAC
 * `session.user.role` は 7 種 (viewer/drafter/reviewer/approver/admin/auditor/guest)。
 * 未知のロールは fail-closed で `"viewer"` に丸める。
 */

// access_token を更新前にこの秒数だけ前倒しで refresh する
const REFRESH_BEFORE_EXPIRY_SECONDS = 60;

// backend /api/v1/auth/me は初回に Cloudflare 証明書取得 + JIT プロビジョニング +
// 監査書込を行うため、短すぎるタイムアウトは初回サインインを失敗させる。
const BACKEND_REQUEST_TIMEOUT_MS = 15_000;

// 既知ロール (backend `app/models/enums.py::UserRole` と完全一致)
const KNOWN_ROLES = [
  "viewer",
  "drafter",
  "reviewer",
  "approver",
  "admin",
  "auditor",
  "guest",
] as const;
type KnownRole = (typeof KNOWN_ROLES)[number];

function normalizeRole(input: unknown): KnownRole {
  if (typeof input === "string" && (KNOWN_ROLES as readonly string[]).includes(input)) {
    return input as KnownRole;
  }
  // fail-closed: 不明値は最小権限 viewer に落とす
  return "viewer";
}

/**
 * Backend `/api/v1/auth/me` から RBAC 情報を取得する。
 * 失敗時は `null` を返し、呼び出し側で error フラグを立てる (fail-closed)。
 */
async function fetchBackendIdentity(
  accessToken: string | undefined,
): Promise<{ role: KnownRole; departmentId: string | null; userId: string | null } | null> {
  if (!accessToken) return null;
  const baseUrl = process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) return null;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), BACKEND_REQUEST_TIMEOUT_MS);
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
      // server-side fetch in next-auth callback: no caching of identity
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    const body = (await res.json()) as {
      id?: string;
      role?: string;
      department_id?: string | null;
    };
    return {
      role: normalizeRole(body.role),
      departmentId: body.department_id ?? null,
      userId: body.id ?? null,
    };
  } catch {
    return null;
  }
}

export const authConfig = {
  // Edge ランタイム互換のため JWT 戦略を維持
  session: {
    strategy: "jwt",
    // backend 側 refresh_token の上限と一致 (8 時間)
    maxAge: 60 * 60 * 8,
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  providers: [
    // -------------------------------------------------------------------------
    // Cloudflare Access (edge authentication) — primary provider.
    //
    // Cloudflare Access authenticates the user at the edge (email OTP + rule
    // groups) and injects `Cf-Access-Jwt-Assertion` /
    // `Cf-Access-Authenticated-User-Email` on every request that reaches the
    // origin. The origin is only reachable through the tunnel behind Access,
    // so those headers are trustworthy; the backend additionally verifies the
    // JWT cryptographically (see backend `verify_access_jwt`, #63).
    //
    // authorize() reads the headers from the incoming callback request and
    // forwards them to `/api/v1/auth/me`, which returns the resolved identity
    // and RBAC role. No Microsoft / password login is involved.
    // -------------------------------------------------------------------------
    Credentials({
      id: "cloudflare-access",
      name: "Cloudflare Access",
      credentials: {},
      async authorize(_credentials, request) {
        const assertion = request.headers.get("cf-access-jwt-assertion");
        const email = request.headers.get("cf-access-authenticated-user-email");
        if (!assertion || !email) {
          // No Access identity on the request → refuse (fail-closed).
          return null;
        }

        const baseUrl =
          process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!baseUrl) return null;

        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), BACKEND_REQUEST_TIMEOUT_MS);
          const res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/auth/me`, {
            method: "GET",
            headers: {
              // Forward the edge-injected Access identity; the backend verifies
              // the assertion against Cloudflare's public certs.
              "Cf-Access-Jwt-Assertion": assertion,
              "Cf-Access-Authenticated-User-Email": email,
              Accept: "application/json",
            },
            cache: "no-store",
            signal: controller.signal,
          });
          clearTimeout(timeout);
          if (!res.ok) return null;
          const body = (await res.json()) as {
            id?: string;
            email?: string;
            name?: string;
            role?: string;
            department_id?: string | null;
          };
          return {
            id: body.id ?? email,
            email: body.email ?? email,
            name: body.name ?? email,
            // carried into the jwt callback below
            role: normalizeRole(body.role),
            department_id: body.department_id ?? null,
          } as unknown as import("next-auth").User;
        } catch {
          return null;
        }
      },
    }),

    // -------------------------------------------------------------------------
    // Microsoft Entra ID via HENNGE One (OIDC) — retained but only registered
    // when a real client id is configured. This deployment authenticates via
    // Cloudflare Access, so it stays dormant unless Entra is explicitly set up.
    // -------------------------------------------------------------------------
    ...(process.env.AUTH_MICROSOFT_ENTRA_ID_ID &&
    process.env.AUTH_MICROSOFT_ENTRA_ID_ID !==
      "00000000-0000-0000-0000-000000000000"
      ? [
          MicrosoftEntraID({
            clientId: process.env.AUTH_MICROSOFT_ENTRA_ID_ID,
            clientSecret: process.env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            issuer: process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
            authorization: {
              params: {
                scope: "openid profile email offline_access",
                prompt: process.env.AUTH_MICROSOFT_ENTRA_ID_PROMPT,
              },
            },
          }),
        ]
      : []),
  ],

  callbacks: {
    /**
     * ルート保護 (Edge middleware から呼ばれる)。
     */
    authorized({ auth, request }) {
      // Dev bypass: skip SSO when AUTH_DEV_BYPASS=true (never set in production)
      if (process.env.AUTH_DEV_BYPASS === "true") return true;

      const { nextUrl } = request;
      const isLoggedIn = Boolean(auth?.user);
      const isOnLogin = nextUrl.pathname.startsWith("/login");

      if (isOnLogin) {
        if (isLoggedIn) {
          return Response.redirect(new URL("/", nextUrl));
        }
        return true;
      }
      return isLoggedIn;
    },

    /**
     * JWT 生成 / 更新。
     *
     * - 初回サインイン (`account` あり): backend `/api/v1/auth/me` で
     *   role/department_id を解決。失敗時は token.error を立てる。
     * - 通常リクエスト: access_token が期限切れ手前なら refresh する。
     */
    async jwt({ token, account, user }) {
      // --- Cloudflare Access sign-in (Credentials provider) ---
      // No OAuth `account`; the user object already carries the backend-resolved
      // role/department from authorize(). The session is re-established from the
      // edge identity on each sign-in, so no refresh_token bookkeeping is needed.
      if (user && !account) {
        const u = user as unknown as {
          id?: string;
          role?: unknown;
          department_id?: string | null;
        };
        token.role = normalizeRole(u.role);
        token.department_id = u.department_id ?? null;
        if (u.id) token.sub = u.id;
        token.error = undefined;
        token.auth_method = "cloudflare-access";
        // Access sessions are gated by Cloudflare Access at the edge; give the
        // app JWT a short lifetime so revocation at Access propagates quickly.
        token.expires_at = Math.floor(Date.now() / 1000) + 60 * 60;
        return token;
      }

      // Access sessions carry no OAuth refresh_token. When the short-lived app
      // JWT lapses, let the request fall through to middleware, which re-signs
      // the user in from the still-valid edge Access headers — never a refresh
      // error loop.
      if (token.auth_method === "cloudflare-access") {
        return token;
      }

      // --- 初回サインイン ---
      if (account) {
        token.id_token = account.id_token;
        token.access_token = account.access_token;
        token.refresh_token = account.refresh_token;
        token.expires_at =
          typeof account.expires_at === "number"
            ? account.expires_at
            : Math.floor(Date.now() / 1000) + 60 * 15;
        if (user?.id) token.sub = user.id;

        const identity = await fetchBackendIdentity(account.access_token as string | undefined);
        if (identity) {
          token.role = identity.role;
          token.department_id = identity.departmentId;
          if (identity.userId) token.sub = identity.userId;
          token.error = undefined;
        } else {
          // fail-closed: backend で認証できなかった場合は最小権限+error
          token.role = "viewer";
          token.department_id = null;
          token.error = "BackendUnauthorized";
        }
        return token;
      }

      // --- access_token がまだ有効 ---
      const expiresAt = typeof token.expires_at === "number" ? token.expires_at : 0;
      const nowSec = Math.floor(Date.now() / 1000);
      if (expiresAt - REFRESH_BEFORE_EXPIRY_SECONDS > nowSec) {
        return token;
      }

      // --- refresh が必要 ---
      const refreshToken = typeof token.refresh_token === "string" ? token.refresh_token : "";
      if (!refreshToken) {
        token.error = "RefreshAccessTokenError";
        return token;
      }
      const refreshed = await refreshAccessToken(refreshToken);
      if (!refreshed) {
        token.error = "RefreshAccessTokenError";
        return token;
      }
      token.access_token = refreshed.access_token;
      token.id_token = refreshed.id_token ?? token.id_token;
      token.refresh_token = refreshed.refresh_token ?? token.refresh_token;
      token.expires_at = refreshed.expires_at;
      token.error = undefined;
      return token;
    },

    /**
     * クライアントに公開する Session の整形。
     */
    async session({ session, token }) {
      if (session.user) {
        session.user.id = (token.sub as string | undefined) ?? session.user.id;
        session.user.role = normalizeRole(token.role);
        session.user.departmentId =
          (token.department_id as string | null | undefined) ?? null;
        session.user.accessToken = token.access_token as string | undefined;
      }
      // session.error を立てておくとクライアント側 hook が
      // 再ログイン誘導 (signIn 再実行) を判定できる
      if (typeof token.error === "string") {
        session.error = token.error;
      }
      return session;
    },
  },

  // 本番要件: Secure / HttpOnly / SameSite=lax は next-auth v5 既定でカバー。
  // 同一サイト + Subdomain (HENNGE) 跨ぎを許容するため lax を採用 (strict だと
  // OIDC コールバックで cookie が落ちる)。
  trustHost: true,
} satisfies NextAuthConfig;
