/**
 * Compliance page E2E tests.
 *
 * Verifies the compliance check page:
 * - Page heading renders correctly
 * - "適用フレームワーク" card is present with ComplianceChecklist
 * - "検出された是正対象" card is present with ComplianceFindingsTable
 * - Filter selects (framework, status) are present in the findings table
 * - AI disclaimer is displayed
 *
 * Prerequisites:
 *   - Next.js running with AUTH_DEV_BYPASS=true (handled by playwright.config.ts webServer).
 *   - Backend API either running or mocked (tests assert only on page-level structure).
 */
import { expect, test } from "@playwright/test";

test.describe("Compliance", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/compliance");
    // Must not redirect to login when AUTH_DEV_BYPASS=true.
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders page heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /コンプライアンスチェック|コンプライアンス|Compliance/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows framework checklist card", async ({ page }) => {
    // The page includes a Card titled "適用フレームワーク".
    // shadcn CardTitle renders as <div>, not a semantic heading, so match by text.
    await expect(
      page.getByText(/適用フレームワーク/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows findings card", async ({ page }) => {
    // The page includes a Card titled "検出された是正対象".
    // shadcn CardTitle renders as <div>, not a semantic heading, so match by text.
    await expect(
      page.getByText(/検出された是正対象|是正対象/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows findings table or empty state", async ({ page }) => {
    // ComplianceFindingsTable renders a table when items exist, otherwise an empty message.
    const table = page.locator(
      "table, [role='table'], [data-testid='compliance-findings-table']"
    ).first();
    const emptyState = page.getByText(/該当する項目がありません|0\s*件/i).first();

    await expect(table.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });

  test("has framework (law) filter select", async ({ page }) => {
    // ComplianceFindingsTable renders a Select with "すべての法令" as default.
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /すべての法令|建設業法|下請法|電子帳簿|個人情報/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("has status filter select", async ({ page }) => {
    // ComplianceFindingsTable renders a Select with "状態" / compliance statuses.
    const trigger = page
      .getByRole("combobox")
      .filter({ hasText: /状態|すべて|適合|要確認|不適合/i })
      .first();
    await expect(trigger).toBeVisible({ timeout: 5_000 });
  });

  test("shows AI disclaimer", async ({ page }) => {
    // AiDisclaimerInline must appear on AI-generated compliance pages.
    const disclaimer = page
      .getByText(/AI チェック結果は参考情報|参考情報|法務担当者|顧問弁護士/i)
      .first();
    await expect(disclaimer).toBeVisible({ timeout: 5_000 });
  });
});
