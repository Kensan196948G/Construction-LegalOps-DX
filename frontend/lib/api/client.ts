/**
 * Axios API Client for Construction-LegalOps-DX
 *
 * - baseURL: NEXT_PUBLIC_API_URL ?? "/api/v1"
 * - withCredentials: true (HttpOnly Cookie ベース認証想定)
 * - request interceptor: JWT トークンを Authorization ヘッダに付与
 *   - サーバサイド: 呼び出し側が `setAuthTokenProvider` で挿入
 *   - クライアントサイド: next-auth の `getSession()` を lazy import で取得
 * - response interceptor:
 *   - 401 → サインアウト誘導
 *   - RFC 7807 ProblemDetails → ApiError へマップ
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

// ---------------------------------------------------------------------------
// Types — RFC 7807 Problem Details
// ---------------------------------------------------------------------------

export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: Array<{ field: string; message: string }>;
  request_id?: string;
  [key: string]: unknown;
}

/**
 * RFC 7807 ProblemDetails を統一的に扱う独自エラークラス。
 *
 * ネットワーク失敗・タイムアウト・JSON でないレスポンスでもこのクラスに正規化する。
 */
export class ApiError extends Error {
  public readonly type: string;
  public readonly title: string;
  public readonly status: number;
  public readonly detail?: string;
  public readonly instance?: string;
  public readonly errors?: Array<{ field: string; message: string }>;
  public readonly requestId?: string;
  public readonly raw?: unknown;

  constructor(problem: ProblemDetails, raw?: unknown) {
    const title = problem.title ?? "API Error";
    const detail = problem.detail;
    super(detail ? `${title}: ${detail}` : title);
    this.name = "ApiError";
    this.type = problem.type ?? "about:blank";
    this.title = title;
    this.status = problem.status ?? 0;
    this.detail = detail;
    this.instance = problem.instance;
    this.errors = problem.errors;
    this.requestId = problem.request_id;
    this.raw = raw;
  }

  /** バリデーションエラー (422) か */
  public isValidationError(): boolean {
    return this.status === 422;
  }

  /** 認証エラー (401) か */
  public isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** 認可エラー (403) か */
  public isForbidden(): boolean {
    return this.status === 403;
  }

  /** 競合 (楽観ロック / 状態遷移違反) か */
  public isConflict(): boolean {
    return this.status === 409;
  }

  /** ネットワーク・タイムアウト等の transport エラーか */
  public isTransportError(): boolean {
    return this.status === 0;
  }
}

// ---------------------------------------------------------------------------
// Auth token provider
// ---------------------------------------------------------------------------

/**
 * リクエストごとに JWT を返す関数型。
 * サーバサイドでは `setAuthTokenProvider()` 経由で auth() の結果を挿入する。
 */
export type AuthTokenProvider = () => Promise<string | null | undefined>;

let externalTokenProvider: AuthTokenProvider | null = null;

/**
 * Auth & Config Team がサーバ側で next-auth `auth()` を bind するためのフック。
 * 循環依存を避けるため、本ファイルから next-auth を直接 import しない。
 */
export function setAuthTokenProvider(provider: AuthTokenProvider | null): void {
  externalTokenProvider = provider;
}

/**
 * クライアントサイドで next-auth の getSession() を lazy import し、
 * `accessToken` を返す既定のフォールバック実装。
 *
 * Auth & Config Team が `session.accessToken` を session callback で公開する想定。
 */
async function defaultClientTokenProvider(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    // Lazy import to avoid pulling next-auth into the server-only client bundle.
    const mod: unknown = await import(/* webpackIgnore: false */ "next-auth/react").catch(
      () => null,
    );
    if (!mod || typeof mod !== "object") return null;
    const getSession = (mod as { getSession?: () => Promise<unknown> }).getSession;
    if (typeof getSession !== "function") return null;
    // types/next-auth.d.ts では session.user.accessToken に格納される。
    // 念のため session.accessToken も fallback として参照する。
    const session = (await getSession()) as
      | { accessToken?: string; user?: { accessToken?: string } }
      | null;
    return session?.user?.accessToken ?? session?.accessToken ?? null;
  } catch {
    return null;
  }
}

async function resolveToken(): Promise<string | null> {
  if (externalTokenProvider) {
    const t = await externalTokenProvider();
    if (t) return t;
  }
  return defaultClientTokenProvider();
}

// ---------------------------------------------------------------------------
// Sign-out trigger (401)
// ---------------------------------------------------------------------------

let onUnauthorized: (() => void) | null = null;

/**
 * 401 受領時に呼ぶハンドラ。Auth & Config Team が `signOut()` を bind する想定。
 */
export function setOnUnauthorized(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function defaultClientSignOut(): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    const mod = await import("next-auth/react").catch(() => null);
    if (!mod || typeof mod !== "object") {
      window.location.href = "/login";
      return;
    }
    const signOut = (mod as { signOut?: (opts?: unknown) => Promise<unknown> }).signOut;
    if (typeof signOut === "function") {
      await signOut({ callbackUrl: "/login" });
    } else {
      window.location.href = "/login";
    }
  } catch {
    window.location.href = "/login";
  }
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

export const API_BASE_URL =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) || "/api/v1";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// --- Request interceptor: JWT bearer の付与 ---------------------------------

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await resolveToken();
    if (token) {
      config.headers = config.headers ?? {};
      // Axios v1 では headers は AxiosHeaders。set があれば優先する。
      const headers = config.headers as unknown as {
        set?: (k: string, v: string) => void;
      } & Record<string, unknown>;
      if (typeof headers.set === "function") {
        headers.set("Authorization", `Bearer ${token}`);
      } else {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// --- Request interceptor: 自動 Idempotency-Key 付与 -------------------------
//
// POST / PUT / PATCH / DELETE には Idempotency-Key を自動付与する。
// 既に呼出側で `withIdempotencyKey()` 経由でヘッダを設定済みの場合はそれを
// 尊重し、上書きしない。GET / HEAD / OPTIONS には付けない (副作用なし)。

const IDEMPOTENT_METHODS = new Set(["post", "put", "patch", "delete"]);

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const method = (config.method ?? "get").toLowerCase();
  if (!IDEMPOTENT_METHODS.has(method)) return config;

  config.headers = config.headers ?? {};
  const headers = config.headers as unknown as {
    get?: (k: string) => unknown;
    set?: (k: string, v: string) => void;
  } & Record<string, unknown>;

  const existing =
    typeof headers.get === "function"
      ? headers.get("Idempotency-Key")
      : headers["Idempotency-Key"] ?? headers["idempotency-key"];
  if (existing) return config;

  const key = generateIdempotencyKey();
  if (typeof headers.set === "function") {
    headers.set("Idempotency-Key", key);
  } else {
    headers["Idempotency-Key"] = key;
  }
  return config;
});

// --- Response interceptor: ProblemDetails → ApiError 正規化 -----------------

function isProblemDetails(value: unknown): value is ProblemDetails {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    "type" in v || "title" in v || "status" in v || "detail" in v || "instance" in v
  );
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<unknown>) => {
    // Network error / timeout / no response.
    if (!error.response) {
      const apiErr = new ApiError(
        {
          type: "about:blank",
          title: error.code === "ECONNABORTED" ? "Request Timeout" : "Network Error",
          status: 0,
          detail: error.message,
        },
        error,
      );
      return Promise.reject(apiErr);
    }

    const { status, data } = error.response;

    // 401: サインアウト誘導
    if (status === 401) {
      try {
        if (onUnauthorized) {
          onUnauthorized();
        } else if (typeof window !== "undefined") {
          await defaultClientSignOut();
        }
      } catch {
        /* swallow */
      }
    }

    const problem: ProblemDetails = isProblemDetails(data)
      ? { ...(data as ProblemDetails), status: (data as ProblemDetails).status ?? status }
      : {
          type: "about:blank",
          title: error.message || "API Error",
          status,
          detail:
            typeof data === "string"
              ? data
              : data && typeof data === "object" && "message" in data
                ? String((data as { message: unknown }).message)
                : undefined,
        };

    return Promise.reject(new ApiError(problem, error));
  },
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Idempotency-Key 用に簡易 UUID v4 を生成する。
 * crypto.randomUUID が無い環境 (古い Node) でも fall back する。
 */
export function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // RFC4122 v4 fallback
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
}

/**
 * 作成系 POST 用に Idempotency-Key を付与した config を作るユーティリティ。
 */
export function withIdempotencyKey(
  config: AxiosRequestConfig = {},
  key: string = generateIdempotencyKey(),
): AxiosRequestConfig {
  return {
    ...config,
    headers: {
      ...(config.headers ?? {}),
      "Idempotency-Key": key,
    },
  };
}

export default apiClient;
