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
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  testPathIgnorePatterns: ["/node_modules/", "/.next/", "/dist/", "/coverage/"],
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
