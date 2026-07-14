import type { Config } from "jest";
import nextJest from "next/jest.js";

/**
 * Next.js 15 + Jest 統合設定。
 *
 * `next/jest` の `createJestConfig` で SWC によるトランスパイル、
 * 環境変数読み込み、CSS / 画像のモック化が自動構成される。
 *
 * カスタム部分:
 *   - testEnvironment: jsdom (React Testing Library 用)
 *   - moduleNameMapper: `@/*` を frontend root にマップ (tsconfig paths と一致)
 *   - setupFilesAfterEach: jest.setup.ts で MSW / matchers を初期化
 */
const createJestConfig = nextJest({
  dir: "./",
});

const customConfig: Config = {
  // Custom environment extends JSDOMEnvironment and copies Node.js Fetch globals
  // into the jsdom window before MSW 2.x interceptors initialize.
  testEnvironment: "<rootDir>/jest.environment.ts",
  setupFiles: ["<rootDir>/jest.polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    // rettime is ESM-only; provide a CJS stub so MSW 2.x can initialize in Jest
    "^rettime$": "<rootDir>/__mocks__/rettime.js",
    // MSW 2.x + @mswjs/interceptors subpath exports: Jest (CJS) cannot resolve package exports
    "^msw/node$": "<rootDir>/node_modules/msw/lib/node/index.js",
    "^msw/browser$": "<rootDir>/node_modules/msw/lib/browser/index.js",
    "^@mswjs/interceptors/ClientRequest$": "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/ClientRequest/index.cjs",
    "^@mswjs/interceptors/XMLHttpRequest$": "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/XMLHttpRequest/index.cjs",
    "^@mswjs/interceptors/fetch$": "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/fetch/index.cjs",
    "^@mswjs/interceptors/WebSocket$": "<rootDir>/node_modules/@mswjs/interceptors/lib/browser/interceptors/WebSocket/index.cjs",
  },
  // rettime is ESM-only; add it alongside next/jest's default geist exception.
  transformIgnorePatterns: [
    "/node_modules/(?!.pnpm)(?!(geist|rettime)/)",
    "/node_modules/.pnpm/(?!(geist|rettime)@)",
    "^.+\\.module\\.(css|sass|scss)$",
  ],
  testPathIgnorePatterns: ["/node_modules/", "/.next/", "/dist/", "/coverage/", "/e2e/"],
  collectCoverageFrom: [
    "app/**/*.{ts,tsx}",
    "components/**/*.{ts,tsx}",
    "lib/**/*.{ts,tsx}",
    "hooks/**/*.{ts,tsx}",
    "!**/*.d.ts",
    "!**/node_modules/**",
  ],
  coverageDirectory: "coverage",
  clearMocks: true,
};

export default createJestConfig(customConfig);
