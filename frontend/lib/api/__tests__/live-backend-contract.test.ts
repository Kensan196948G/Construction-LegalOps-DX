import { z } from "zod";

import {
  contractSchema,
  disputeSchema,
  legalReviewSchema,
  paginatedSchema,
  paymentComplianceSchema,
  retentionRuleSchema,
  riskItemSchema,
  workflowApplicationSchema,
} from "@/lib/api/schemas";

/**
 * 実バックエンドに対する契約（zod schema）整合チェック。
 *
 * 2026-09-28 に「frontend の zod が backend の実レスポンスと一致せず、画面が
 * 黙って空/エラーになる」不具合が 2 件（/payments の payment-compliance、
 * /dashboard の承認待ち）見つかった。同型のズレを機械的に再発見するための網。
 *
 * **CI では実行しない**（ネットワーク依存のため）。`MVP_API_URL` を設定した
 * ときだけ走る:
 *
 * ```
 * MVP_API_URL=http://127.0.0.1:8013/api/v1 \
 *   npx jest lib/api/__tests__/live-backend-contract.test.ts
 * ```
 */

const BASE = process.env.MVP_API_URL;
const describeLive = BASE ? describe : describe.skip;

const LIST_CASES: Array<{ name: string; path: string; schema: z.ZodTypeAny }> = [
  {
    name: "contracts",
    path: "/contracts?page=1&size=50",
    schema: paginatedSchema(contractSchema),
  },
  {
    name: "reviews",
    path: "/reviews?page=1&size=50",
    schema: paginatedSchema(legalReviewSchema),
  },
  {
    name: "risks",
    path: "/risks?page=1&size=50",
    schema: paginatedSchema(riskItemSchema),
  },
  {
    name: "disputes",
    path: "/disputes?page=1&size=50",
    schema: paginatedSchema(disputeSchema),
  },
  {
    name: "workflow-applications",
    path: "/workflows/applications?page=1&size=50",
    schema: paginatedSchema(workflowApplicationSchema),
  },
  {
    name: "retention-rules",
    path: "/retention/rules",
    schema: z.array(retentionRuleSchema),
  },
];

describeLive("live backend contract compatibility", () => {
  it("main list endpoints parse with the frontend schemas", async () => {
    for (const testCase of LIST_CASES) {
      const res = await fetch(`${BASE}${testCase.path}`);
      const body = await res.json().catch(() => null);
      const parsed = testCase.schema.safeParse(body);
      expect({
        endpoint: testCase.name,
        status: res.status,
        issues: parsed.success ? [] : parsed.error.issues,
      }).toEqual({ endpoint: testCase.name, status: 200, issues: [] });
    }
  }, 120_000);

  it("every contract payment-compliance response parses", async () => {
    const listRes = await fetch(`${BASE}/contracts?page=1&size=200`);
    const list = (await listRes.json()) as { items: Array<{ id: number }> };
    expect(list.items.length).toBeGreaterThan(0);

    const failures: Array<{ contract_id: number; issues: unknown }> = [];
    for (const { id } of list.items) {
      const res = await fetch(`${BASE}/contracts/${id}/payment-compliance`);
      const body = await res.json();
      const parsed = paymentComplianceSchema.safeParse(body);
      if (!parsed.success) {
        failures.push({ contract_id: id, issues: parsed.error.issues });
      }
    }
    expect(failures).toEqual([]);
  }, 180_000);
});
