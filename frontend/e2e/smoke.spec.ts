/**
 * Smoke tests — verify each major page renders without JS errors.
 *
 * Prerequisites:
 *   - Next.js running with AUTH_DEV_BYPASS=true (handled by playwright.config.ts webServer).
 *   - Backend API either running or mocked (tests assert only on page-level structure).
 *
 * These tests exercise the golden path: page loads → H1/heading visible → no uncaught error.
 */
import { expect, test } from "@playwright/test";

// Pages that should be accessible with AUTH_DEV_BYPASS=true (no SSO redirect).
const PAGES = [
  { path: "/dashboard", heading: /ダッシュボード|Dashboard/i },
  { path: "/contracts", heading: /契約|Contract/i },
  { path: "/reviews", heading: /レビュー|Review/i },
  { path: "/workflows", heading: /ワークフロー|Workflow/i },
  { path: "/risks", heading: /リスク|Risk/i },
  { path: "/compliance", heading: /コンプライアンス|Compliance/i },
  { path: "/templates", heading: /ひな形|テンプレート|Template/i },
  { path: "/knowledge", heading: /ナレッジ|Knowledge/i },
  { path: "/audit-logs", heading: /監査|Audit/i },
];

test.describe("Smoke — page renders", () => {
  for (const { path, heading } of PAGES) {
    test(`${path} renders without error`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(path);

      // Must not redirect to login when AUTH_DEV_BYPASS=true.
      await expect(page).not.toHaveURL(/\/login/);

      // A heading matching the page name must exist.
      await expect(page.getByRole("heading", { name: heading })).toBeVisible({
        timeout: 10_000,
      });

      // No uncaught JS errors.
      expect(errors, `Uncaught JS errors on ${path}: ${errors.join(", ")}`).toHaveLength(0);
    });
  }
});
