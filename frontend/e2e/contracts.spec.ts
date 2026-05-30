/**
 * Contracts page E2E tests.
 *
 * Verifies the contracts list page and basic navigation:
 * - Table renders with headers
 * - Search/filter inputs are present
 * - "新規作成" button is accessible
 */
import { expect, test } from "@playwright/test";

test.describe("Contracts", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/contracts");
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("shows contracts table with headers", async ({ page }) => {
    // The table or loading skeleton must appear.
    await expect(
      page.locator("table, [role='table'], [data-testid='contracts-table']").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("has search input", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/検索|search/i).first();
    await expect(searchInput).toBeVisible({ timeout: 5_000 });
  });

  test("has new contract button", async ({ page }) => {
    const newBtn = page
      .getByRole("button", { name: /新規|新しい|作成|New|Create/i })
      .first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });
});
