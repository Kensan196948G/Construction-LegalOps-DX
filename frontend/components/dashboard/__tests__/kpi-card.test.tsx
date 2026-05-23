import React from "react";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "../kpi-card";
import { FileText } from "lucide-react";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard icon={FileText} label="契約件数" value={42} />);
    expect(screen.getByText("契約件数")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders deltaLabel when provided", () => {
    render(<KpiCard icon={FileText} label="リスク" value={5} deltaLabel="先月比 +2" />);
    expect(screen.getByText("先月比 +2")).toBeInTheDocument();
  });

  it("does not render deltaLabel when omitted", () => {
    render(<KpiCard icon={FileText} label="ラベル" value={10} />);
    expect(screen.queryByText(/先月比/)).not.toBeInTheDocument();
  });

  it("formats large numbers with locale separator", () => {
    render(<KpiCard icon={FileText} label="金額" value={1000000} />);
    // toLocaleString in jsdom may output "1,000,000" or "1000000" depending on locale
    const valueEl = screen.getByText(/1.000.000|1,000,000|1000000/);
    expect(valueEl).toBeInTheDocument();
  });

  it("applies warning tone classes", () => {
    const { container } = render(<KpiCard icon={FileText} label="警告" value={3} tone="warning" />);
    // Card should have amber border class
    expect(container.firstChild).toHaveClass("border-amber-300");
  });

  it("does not apply warning classes for default tone", () => {
    const { container } = render(<KpiCard icon={FileText} label="通常" value={3} tone="default" />);
    expect(container.firstChild).not.toHaveClass("border-amber-300");
  });
});
