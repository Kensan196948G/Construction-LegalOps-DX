import type { DefaultSession } from "next-auth";

/**
 * next-auth v5 module augmentation。
 *
 * Construction-LegalOps-DX では Session / JWT に以下を持たせる:
 *   - user.id            : Entra ID OID (Backend のユーザ ID と一致させる)
 *   - user.role          : RBAC ロール (`admin` | `legal_manager` | `legal_reviewer` | `viewer` ...)
 *   - user.departmentId  : 部門 ID (法務部の階層判定で利用)
 *   - user.accessToken   : Backend `/api/v1/*` 呼び出し用 Bearer Token
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
    expires_at?: number;
    role?: string;
    department_id?: string | null;
  }
}
