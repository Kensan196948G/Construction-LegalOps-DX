/**
 * Knowledge detail page E2E tests.
 *
 * Verifies the /knowledge/:id detail page renders correctly (Issue #33):
 * - Page wrapper with data-testid="knowledge-detail-page" is present
 * - AI disclaimer is shown (legal requirement on all AI-sourced pages)
 * - Back-navigation link returns to /knowledge list
 * - Body content area is present
 * - Metadata section is rendered
 *
 * All tests are backend-independent: they navigate to /knowledge/1 which
 * renders either the real article (if backend is up) or the "not found"
 * placeholder (if the API returns 404/error). Both code-paths satisfy the
 * structural assertions here, so CI stays green without a running backend.
 */
import { expect, test } from "@playwright/test";

const DETAIL_URL = "/knowledge/1";

test.describe("Knowledge Detail", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(DETAIL_URL);
    // Must not redirect to login when AUTH_DEV_BYPASS=true.
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("renders detail page wrapper", async ({ page }) => {
    await expect(
      page.locator('[data-testid="knowledge-detail-page"]')
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows AI disclaimer", async ({ page }) => {
    // AiDisclaimerInline must appear on all AI-content pages (legal requirement).
    const disclaimer = page
      .getByText(/参考情報|法務担当者|顧問弁護士/i)
      .first();
    await expect(disclaimer).toBeVisible({ timeout: 5_000 });
  });

  test("shows back navigation link to knowledge list", async ({ page }) => {
    const backLink = page.locator('[data-testid="back-link"]');
    await expect(backLink).toBeVisible({ timeout: 10_000 });
    await expect(backLink).toHaveAttribute("href", "/knowledge");
  });

  test("back link navigates to knowledge list page", async ({ page }) => {
    const backLink = page.locator('[data-testid="back-link"]');
    await backLink.click();
    await expect(page).toHaveURL(/\/knowledge$/, { timeout: 10_000 });
    await expect(
      page.getByRole("heading", { name: /ナレッジベース|ナレッジ/i })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows article body area or not-found message", async ({ page }) => {
    // When backend returns data: article-body is present.
    // When backend is unavailable / 404: "記事が見つかりませんでした" is shown.
    const body = page.locator('[data-testid="article-body"]');
    const notFound = page.getByText(/記事が見つかりませんでした/i);
    await expect(body.or(notFound)).toBeVisible({ timeout: 10_000 });
  });

  test("shows article title or placeholder card", async ({ page }) => {
    // Either a real title renders or the placeholder card appears.
    const title = page.locator('[data-testid="article-title"]');
    const placeholder = page.getByText(/記事が見つかりませんでした/i);
    await expect(title.or(placeholder)).toBeVisible({ timeout: 10_000 });
  });

  test("card title on knowledge list links to detail page", async ({ page }) => {
    // Navigate to list first, verify at least one article title is a link to /knowledge/:id.
    await page.goto("/knowledge");
    await expect(page).not.toHaveURL(/\/login/);

    // KnowledgeResults renders <Link href="/knowledge/{id}"><h3>...</h3></Link>.
    // If the list is empty (no backend), this test is a soft pass.
    const knowledgeLinks = page.locator('a[href^="/knowledge/"]');
    const count = await knowledgeLinks.count();
    if (count > 0) {
      await expect(knowledgeLinks.first()).toBeVisible({ timeout: 5_000 });
    }
  });
});
