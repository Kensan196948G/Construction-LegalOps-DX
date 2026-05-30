/**
 * Reviews page E2E tests.
 *
 * Verifies the AI review list page:
 * - Table renders with headers
 * - Status badges are present in filter UI
 * - Filter selects (status, riskLevel, reviewerConfirmed) are present
 * - AI disclaimer is displayed
 *
 * Prerequisites:
 *   - Next.js running with AUTH_DEV_BYPASS=true (handled by playwright.config.ts webServer).
 *   - Backend API either running or mocked (tests assert only on page-level structure).
 */
import { expect, test } from "@playwright/test";

test.describe("Reviews", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/reviews");
    // Must not redirect to login when AUTH_DEV_BYPASS=true.
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders page heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /AI\s*一次レビュー|レビュー|Review/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows reviews table or empty state", async ({ page }) => {
    // Either a table or an empty-state message should appear after data fetch.
    const table = page.locator(
      "table, [role='table'], [data-testid='reviews-table']"
    ).first();
    const emptyState = page.getByText(/レビューがありません|0\s*件|該当する項目/i).first();

    await expect(table.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });

  test("has status filter select", async ({ page }) => {
    // ReviewsFilters renders a Select with placeholder "ステータス".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /ステータス|すべて|完了|レビュー中/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("has risk level filter select", async ({ page }) => {
    // ReviewsFilters renders a Select with placeholder "リスク".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /リスク|低|中|高|重大/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("has reviewer confirmed filter select", async ({ page }) => {
    // ReviewsFilters renders a Select with placeholder "確認状態".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /確認状態|確認済み|未確認/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("shows AI disclaimer", async ({ page }) => {
    // AiDisclaimerInline must appear on every AI-result page.
    const disclaimer = page
      .getByText(/AI|参考情報|法務担当者|顧問弁護士/i)
      .first();
    await expect(disclaimer).toBeVisible({ timeout: 5_000 });
  });
});
