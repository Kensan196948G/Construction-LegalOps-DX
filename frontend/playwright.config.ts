import { defineConfig, devices } from "@playwright/test";

/**
 * Construction LegalOps DX — Playwright E2E configuration.
 *
 * AUTH_DEV_BYPASS=true  : Next.js middleware skips SSO, used for local/CI E2E.
 * BASE_URL env          : Override the base URL (default: http://localhost:3000).
 */
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // next.config.mjs uses `output: "standalone"`, which `next start` cannot serve.
    // start:standalone copies static/public into .next/standalone (mirrors the
    // Dockerfile) and runs the standalone server on PORT=3000 to match baseURL.
    command: "AUTH_DEV_BYPASS=true npm run start:standalone",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      AUTH_DEV_BYPASS: "true",
      AUTH_SECRET: "playwright-local-placeholder-secret",
      NEXTAUTH_SECRET: "playwright-local-placeholder-secret",
    },
  },
});
