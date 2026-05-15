/**
 * Environment variable typing for Construction-LegalOps-DX frontend.
 *
 * NEXT_PUBLIC_* のみクライアントバンドルに露出される。
 * その他はサーバサイド (server actions / route handlers / middleware) でのみ参照可。
 */

// eslint-disable-next-line @typescript-eslint/no-namespace
declare namespace NodeJS {
  interface ProcessEnv {
    // --- Runtime ---
    readonly NODE_ENV: "development" | "test" | "production";

    // --- API ---
    /** API のベース URL。未設定時は /api/v1 (Next.js rewrite で backend へプロキシ想定)。 */
    readonly NEXT_PUBLIC_API_URL?: string;

    // --- Auth (next-auth / Entra ID) — Auth & Config Team が設定する想定 ---
    readonly NEXTAUTH_URL?: string;
    readonly NEXTAUTH_SECRET?: string;
    readonly AUTH_AZURE_AD_CLIENT_ID?: string;
    readonly AUTH_AZURE_AD_CLIENT_SECRET?: string;
    readonly AUTH_AZURE_AD_TENANT_ID?: string;

    // --- Observability ---
    readonly NEXT_PUBLIC_APP_VERSION?: string;
    readonly NEXT_PUBLIC_SENTRY_DSN?: string;

    // --- Feature flags ---
    readonly NEXT_PUBLIC_ENABLE_DEVTOOLS?: "true" | "false";
  }
}

export {};
