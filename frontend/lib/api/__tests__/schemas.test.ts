import {
  contractSchema,
  legalReviewSchema,
  paymentComplianceSchema,
  workflowApplicationSchema,
} from "@/lib/api/schemas";

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

  /**
   * Regression (/payments が全契約で「API 未接続」):
   * backend `PaymentFindingOut` は {code, severity, message, citation, detail} を
   * 返すが、旧 frontend schema は {code, title, severity, description, citation} を
   * 要求していたため、zod parse が必ず失敗し offline 表示になっていた。
   * `overall_status` も backend は fail | warning | pass の 3 値（旧 schema は
   * warn | block という存在しない値域だった）。
   */
  it("accepts real backend payment-compliance payload (fail/warning/pass)", () => {
    // MVP `GET /contracts/44/payment-compliance` の実レスポンス（2026-09-28 実測）
    const parsed = paymentComplianceSchema.safeParse({
      contract_id: 44,
      order_date: null,
      receipt_date: null,
      inspection_date: null,
      payment_date: null,
      transaction_kind: null,
      is_public_work: false,
      law_version: "unknown",
      applicable_threshold_days: 60,
      days_receipt_to_payment: null,
      days_inspection_to_payment: null,
      late_interest_jpy: "0",
      overall_status: "warning",
      findings: [
        {
          code: "payment_order_date_unknown",
          severity: "warn",
          message: "発注日が未設定のため新旧法（取適法/旧下請法）の適用判定ができません。",
          citation: "取適法 附則（2026-01-01 施行）",
          detail: {},
        },
      ],
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.overall_status).toBe("warning");
      expect(parsed.data.findings[0]?.message).toContain("発注日が未設定");
      expect(parsed.data.findings[0]?.detail).toEqual({});
    }
  });

  it("accepts every payment overall_status the backend can emit", () => {
    for (const overall_status of ["pass", "warning", "fail"] as const) {
      const parsed = paymentComplianceSchema.safeParse({
        contract_id: 1,
        law_version: "toritekihou",
        applicable_threshold_days: 60,
        late_interest_jpy: "0",
        overall_status,
      });
      expect(parsed.success).toBe(true);
    }
    // 旧 schema の値域（warn / block）は backend には存在しないので拒否される
    expect(
      paymentComplianceSchema.safeParse({
        contract_id: 1,
        law_version: "toritekihou",
        applicable_threshold_days: 60,
        late_interest_jpy: "0",
        overall_status: "block",
      }).success,
    ).toBe(false);
  });

  it("accepts every payment finding severity the backend can emit", () => {
    for (const severity of ["block", "warn", "info"] as const) {
      const parsed = paymentComplianceSchema.safeParse({
        contract_id: 1,
        law_version: "toritekihou",
        applicable_threshold_days: 60,
        late_interest_jpy: "0",
        overall_status: "pass",
        findings: [
          { code: "x", severity, message: "m", citation: "c", detail: { k: 1 } },
        ],
      });
      expect(parsed.success).toBe(true);
    }
  });
});
