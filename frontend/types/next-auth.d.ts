import type { DefaultSession } from "next-auth";

/**
 * next-auth v5 module augmentation。
 *
 * Construction-LegalOps-DX では Session / JWT に以下を持たせる:
 *   - user.id            : Entra ID OID (Backend のユーザ ID と一致させる)
 *   - user.role          : RBAC ロール (`viewer` | `drafter` | `reviewer` |
 *                          `approver` | `admin` | `auditor` | `guest`)
 *   - user.departmentId  : 部門 ID (法務部の階層判定で利用)
 *   - user.accessToken   : Backend `/api/v1/*` 呼び出し用 Bearer Token
 *   - session.error      : `RefreshAccessTokenError` / `BackendUnauthorized` 等
 *                          クライアント側で再ログイン誘導に使うエラーコード
 *
 * 実値は `auth.config.ts` の `jwt` / `session` callback で設定される。
 */
declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role: string;
      departmentId: string | null;
      accessToken?: string;
    } & DefaultSession["user"];
    /**
     * BackendUnauthorized / RefreshAccessTokenError 等のエラーコード。
     * クライアント hook が再ログイン誘導の判定に利用する。
     */
    error?: string;
  }

  interface User {
    role?: string;
    departmentId?: string | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id_token?: string;
    access_token?: string;
    /** OIDC 経由で取得する refresh_token (offline_access scope 必須) */
    refresh_token?: string;
    /** access_token の有効期限 (UNIX epoch 秒) */
    expires_at?: number;
    /**
     * `next-auth` 既定の慣習互換: ミリ秒単位の有効期限を保持したい場合に利用。
     * 本プロジェクトでは秒単位の `expires_at` を主に使うが、互換のため optional で保持する。
     */
    accessTokenExpires?: number;
    /** RBAC ロール (`normalizeRole` で正規化済み) */
    role?: string;
    /** 部門 ID。未解決の場合は null。 */
    department_id?: string | null;
    /**
     * `lib/auth/session-bridge` / Backend と命名揃え用 alias。
     * `auth.config.ts` 内部では `department_id` を主に使うが、
     * 一部 hook が `departmentId` を参照する場合に備える。
     */
    departmentId?: string;
    /**
     * `BackendUnauthorized` / `RefreshAccessTokenError` 等のエラーコード。
     * session callback でクライアントへ伝搬される。
     */
    error?: string;
    /**
     * 認証方式。`"cloudflare-access"` の場合は OAuth refresh を行わず、
     * 期限切れ時は middleware がエッジの Access identity から再サインインする。
     */
    auth_method?: string;
  }
}
