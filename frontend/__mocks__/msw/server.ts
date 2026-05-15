import { setupServer } from "msw/node";

import { handlers } from "./handlers";

/**
 * Jest (Node) 用 MSW サーバー。
 *
 * - `jest.setup.ts` から listen / resetHandlers / close を呼び出す
 * - 個別テストで `server.use(http.get(..., ...))` のようにオーバーライド可
 */
export const server = setupServer(...handlers);
