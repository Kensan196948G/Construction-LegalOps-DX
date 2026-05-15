"use client";

/**
 * TanStack Query Provider
 *
 * - QueryClient はモジュールスコープで生成しないこと (SSR で複数リクエスト間の共有を避ける)。
 * - <HydrationBoundary> でサーバ側 prefetch を受け渡せるよう state prop を受け取る。
 * - ReactQueryDevtools は import 時 dev only にする。
 */

import {
  HydrationBoundary,
  QueryClient,
  QueryClientProvider,
  type DehydratedState,
} from "@tanstack/react-query";
import { lazy, Suspense, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";
import { useInitApiClient } from "@/lib/api/init-client";

// devtools は optional dep として扱う。未インストールでも本コンポーネントが動作するよう
// 動的 import の specifier を式経由で渡し、型解決を任意化する。
const ReactQueryDevtools =
  process.env.NODE_ENV === "development"
    ? lazy(async () => {
        try {
          const moduleId = "@tanstack/react-query-devtools";
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mod: any = await (Function(
            "id",
            "return import(id)",
          ) as (id: string) => Promise<unknown>)(moduleId);
          return { default: mod.ReactQueryDevtools };
        } catch {
          // フォールバック: no-op コンポーネント
          return { default: () => null };
        }
      })
    : null;

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // クライアント側で 30 秒は stale 扱いしない。リスト/詳細多用のため強めの cache。
        staleTime: 30 * 1000,
        gcTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // 4xx は再試行しない。401/403/404/409/422 はサーバ起因の業務エラー。
          if (error instanceof ApiError) {
            if (error.status >= 400 && error.status < 500) return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    // サーバ: リクエストごとに新規 (props で渡せる setup を考慮)
    return makeQueryClient();
  }
  // ブラウザ: 単一インスタンスを再利用
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export interface QueryProviderProps {
  children: ReactNode;
  /** サーバ側で dehydrate した状態を渡す場合 */
  state?: DehydratedState;
}

export function QueryProvider({ children, state }: QueryProviderProps): JSX.Element {
  // useState の初期化子で 1 度だけ生成する (SSR-safe)
  const [client] = useState(() => getQueryClient());

  // next-auth `useSession()` → API client への token bridge を install。
  // `SessionProvider` 未配置時は session-bridge 側で握り潰す。
  useInitApiClient();

  return (
    <QueryClientProvider client={client}>
      <HydrationBoundary state={state}>{children}</HydrationBoundary>
      {ReactQueryDevtools ? (
        <Suspense fallback={null}>
          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
        </Suspense>
      ) : null}
    </QueryClientProvider>
  );
}

export default QueryProvider;
