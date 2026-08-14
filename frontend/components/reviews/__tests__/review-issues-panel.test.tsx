import { render, screen } from "@testing-library/react";
import { ReviewIssuesPanel } from "@/components/reviews/review-issues-panel";
import type { ReviewFinding } from "@/lib/api/schemas";

function finding(overrides: Partial<ReviewFinding> = {}): ReviewFinding {
  return {
    clause_seq: 3,
    title: "契約金額・支払条件",
    risk_level: "high",
    comment: "支払期日が60日を超えており、下請法第2条の4に違反する可能性があります。",
    suggestion: "支払期日を60日以内に短縮する。",
    citations: ["下請法 第2条の4"],
    verdict: "finding",
    ...overrides,
  };
}

describe("ReviewIssuesPanel", () => {
  it("shows an honest empty state when no findings exist", () => {
    render(<ReviewIssuesPanel reviewId="1" findings={[]} />);
    expect(screen.getByText(/指摘はまだありません/)).toBeInTheDocument();
  });

  it("renders findings from API data instead of mocks", () => {
    render(<ReviewIssuesPanel reviewId="1" findings={[finding()]} />);
    expect(screen.getByText("契約金額・支払条件")).toBeInTheDocument();
    expect(screen.getByText(/下請法第2条の4/)).toBeInTheDocument();
    expect(screen.getByText(/推奨対応/)).toBeInTheDocument();
  });
});
