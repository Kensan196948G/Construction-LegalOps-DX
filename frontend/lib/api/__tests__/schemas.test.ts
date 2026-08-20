import { contractSchema, legalReviewSchema, workflowApplicationSchema } from "@/lib/api/schemas";

/**
 * Regression: backend serializes Decimal as strings and ReviewStatus includes
 * "pending". These schemas must accept the real MVP payloads (SSR pages were
 * rendering empty because parsing threw).
 */
describe("API schema compatibility with backend payloads", () => {
  it("accepts Decimal-as-string contract amount", () => {
    const parsed = contractSchema.safeParse({
      id: 45,
      contract_no: "CTR-2026-0001",
      title: "工事請負契約（デモ）",
      contract_type: "工事請負契約",
      amount: "1200000.00",
      status: "draft",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.amount).toBe(1200000);
    }
  });

  it("accepts workflow application Decimal-as-string amount", () => {
    const parsed = workflowApplicationSchema.safeParse({
      step_id: 61,
      contract_id: 45,
      title: "工事請負契約（デモ）",
      contract_type: "工事請負契約",
      amount: "3500000.00",
      step_name: "法務レビュー",
      step_type: "legal_review",
      status: "pending",
      submitted_at: "2026-08-14T00:00:00Z",
    });
    expect(parsed.success).toBe(true);
  });

  it("accepts backend review status 'pending'", () => {
    const parsed = legalReviewSchema.safeParse({
      id: 45,
      contract_id: 59,
      review_type: "hybrid",
      status: "pending",
      ai_model: "deepseek-chat",
      risk_score: 70,
    });
    expect(parsed.success).toBe(true);
  });
});
