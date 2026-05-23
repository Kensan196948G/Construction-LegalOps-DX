/**
 * Jest setup (executed before each test file).
 *
 * - `@testing-library/jest-dom` で `toBeInTheDocument` 等の matcher を有効化
 * - MSW (Node) サーバーを起動し API レイヤをモック化
 * - `next-auth` の `auth` / `signIn` / `signOut` をデフォルトでモックし、
 *   各テストで `jest.mocked(auth).mockResolvedValue(...)` 等で差し替え可能とする
 */

import "@testing-library/jest-dom";

import { server } from "./__mocks__/msw/server";

// ---------------------------------------------------------------------------
// MSW lifecycle
// ---------------------------------------------------------------------------
beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

// ---------------------------------------------------------------------------
// next-auth mocks (Server Component / Route Handler 用)
// 個別テストで `jest.mocked(...).mockResolvedValue(session)` のように上書きする
// ---------------------------------------------------------------------------
jest.mock("@/auth", () => ({
  auth: jest.fn(async () => null),
  signIn: jest.fn(async () => undefined),
  signOut: jest.fn(async () => undefined),
  handlers: { GET: jest.fn(), POST: jest.fn() },
}));

// next/navigation の Server Component 依存 API も最低限モック (Components Team が拡張可)
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  redirect: jest.fn(),
  notFound: jest.fn(),
}));
