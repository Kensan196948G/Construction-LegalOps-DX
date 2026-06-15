/**
 * Knowledge base page E2E tests.
 *
 * Verifies the knowledge search page (Issue #20 — E2E 詳細テスト拡充):
 * - Page heading renders correctly
 * - AI disclaimer is displayed (legal requirement on AI-summarised pages)
 * - Search bar (input + submit button) is present and drives a query navigation
 * - Category navigation (カテゴリ / ソース種別) renders and filters via the URL
 * - Results section shows either a result count or the empty/prompt state
 *
 * Prerequisites:
 *   - Next.js running with AUTH_DEV_BYPASS=true (handled by playwright.config.ts webServer).
 *   - Backend API either running or mocked (tests assert only on page-level structure,
 *     so they remain green whether or not the knowledge API returns data).
 */
import { expect, test } from "@playwright/test";

test.describe("Knowledge", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/knowledge");
    // Must not redirect to login when AUTH_DEV_BYPASS=true.
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders page heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /ナレッジベース|ナレッジ|Knowledge/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows AI disclaimer", async ({ page }) => {
    // AiDisclaimerInline must appear on AI-summarised knowledge pages.
    const disclaimer = page
      .getByText(/参考情報|法務担当者|顧問弁護士/i)
      .first();
    await expect(disclaimer).toBeVisible({ timeout: 5_000 });
  });

  test("shows search bar with input and submit button", async ({ page }) => {
    await expect(
      page.getByPlaceholder(/キーワード検索|判例|社内文書|FAQ/i)
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByRole("button", { name: /検索/ })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("search submits the query into the URL", async ({ page }) => {
    const input = page.getByPlaceholder(/キーワード検索|判例|社内文書|FAQ/i);
    await input.fill("下請");
    await page.getByRole("button", { name: /検索/ }).click();

    // KnowledgeSearchBar pushes the query into the q= search param.
    await expect(page).toHaveURL(/[?&]q=/, { timeout: 10_000 });
  });

  test("shows category navigation", async ({ page }) => {
    // Sidebar Card titled カテゴリ plus the ソース種別 group.
    // KnowledgeCategoryNav renders the label as <p>, not a heading — match by text.
    await expect(
      page.getByText(/カテゴリ/i).first()
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/ソース種別/i).first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("category link filters via the URL", async ({ page }) => {
    // KnowledgeCategoryNav renders Links such as 建設業法 → ?category=建設業法.
    // Scope to category= hrefs so we don't grab a result-card link with the same text.
    await page
      .locator('a[href*="category="]')
      .filter({ hasText: "建設業法" })
      .first()
      .click();
    await expect(page).toHaveURL(/[?&]category=/, { timeout: 10_000 });
  });

  test("source-type link filters via the URL", async ({ page }) => {
    // ソース種別 list contains 判例 → ?source=precedent.
    await page.getByRole("link", { name: "判例" }).first().click();
    await expect(page).toHaveURL(/[?&]source=/, { timeout: 10_000 });
  });

  test("shows results count or empty/prompt state", async ({ page }) => {
    // KnowledgeResults renders a "N 件のナレッジが見つかりました" line when items
    // exist, otherwise the prompt to enter a keyword / pick a category.
    const resultCount = page.getByText(/件のナレッジが見つかりました/i).first();
    const emptyState = page
      .getByText(/キーワードを入力するか|カテゴリを選択/i)
      .first();

    await expect(resultCount.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });
});
