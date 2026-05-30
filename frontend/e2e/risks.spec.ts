/**
 * Risks page E2E tests.
 *
 * Verifies the risk management page:
 * - Page heading renders correctly
 * - Summary card (サマリー) is present
 * - Risk overview / heatmap area is present
 * - Filter selects (level, category, status) are present
 * - Table or empty state is displayed
 * - AI disclaimer is shown
 *
 * Prerequisites:
 *   - Next.js running with AUTH_DEV_BYPASS=true (handled by playwright.config.ts webServer).
 *   - Backend API either running or mocked (tests assert only on page-level structure).
 */
import { expect, test } from "@playwright/test";

test.describe("Risks", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/risks");
    // Must not redirect to login when AUTH_DEV_BYPASS=true.
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders page heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /リスク管理|リスク|Risk/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows summary card", async ({ page }) => {
    // The page wraps RisksOverview in a Card with title "サマリー".
    await expect(
      page.getByRole("heading", { name: /サマリー/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows risks overview area", async ({ page }) => {
    // RisksOverview renders bar/chart elements or heatmap cells.
    // Accept either a visual chart container or an overview section.
    const overview = page
      .locator('[class*="overview"], [class*="heatmap"], [class*="chart"], [class*="summary"]')
      .first();
    const card = page.locator('[class*="card"]').first();
    await expect(overview.or(card)).toBeVisible({ timeout: 10_000 });
  });

  test("shows risks table or empty state", async ({ page }) => {
    const table = page.locator(
      "table, [role='table'], [data-testid='risks-table']"
    ).first();
    const emptyState = page.getByText(/リスクがありません|0\s*件|該当する項目/i).first();

    await expect(table.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });

  test("has risk level filter select", async ({ page }) => {
    // RisksFilters renders a Select with placeholder "レベル".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /レベル|低|中|高|重大/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("has category filter select", async ({ page }) => {
    // RisksFilters renders a Select with placeholder "カテゴリ".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /カテゴリ|建設業法|下請法/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("has status filter select", async ({ page }) => {
    // RisksFilters renders a Select with placeholder "状態".
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /状態|未対応|軽減済み|受容|解消/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("shows AI disclaimer", async ({ page }) => {
    // AiDisclaimerInline must appear on AI-generated risk pages.
    const disclaimer = page
      .getByText(/リスクスコアは AI|参考情報|法務担当者|顧問弁護士/i)
      .first();
    await expect(disclaimer).toBeVisible({ timeout: 5_000 });
  });
});
