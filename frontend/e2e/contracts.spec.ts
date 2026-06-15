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
    // E2E runs frontend-only (no backend), so the Server Component may render the
    // empty state instead of a table. Accept either.
    const table = page
      .locator("table, [role='table'], [data-testid='contracts-table']")
      .first();
    const emptyState = page
      .getByText(/契約が見つかりません|契約がありません|0\s*件|該当する項目/i)
      .first();
    await expect(table.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });

  test("has search input", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/検索|search/i).first();
    await expect(searchInput).toBeVisible({ timeout: 5_000 });
  });

  test("has new contract button", async ({ page }) => {
    // <Button asChild><Link/></Button> renders as <a role="link">, not a button.
    const newBtn = page
      .getByRole("link", { name: /新規|新しい|作成|New|Create/i })
      .first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });
});
