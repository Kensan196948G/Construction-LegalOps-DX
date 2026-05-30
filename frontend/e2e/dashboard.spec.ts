/**
 * Dashboard page E2E tests.
 *
 * Verifies KPI cards and quick-links render on the dashboard.
 */
import { expect, test } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders KPI card area", async ({ page }) => {
    // At least one card / stat container should be visible.
    const card = page
      .locator('[class*="card"], [class*="stat"], [class*="kpi"], article')
      .first();
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  test("navigation sidebar visible", async ({ page }) => {
    // Sidebar nav link to contracts should be present.
    const contractsLink = page.getByRole("link", { name: /契約|contract/i }).first();
    await expect(contractsLink).toBeVisible({ timeout: 5_000 });
  });

  test("page title present", async ({ page }) => {
    await expect(page).toHaveTitle(/LegalOps|建設|法務/i);
  });
});
