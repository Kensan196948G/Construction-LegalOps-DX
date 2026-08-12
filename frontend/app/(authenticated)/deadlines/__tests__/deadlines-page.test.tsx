import React from "react";
import { render, screen } from "@testing-library/react";

import DeadlinesPage from "../page-client";

jest.mock("next/link", () => {
  const MockLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

function futureDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

describe("DeadlinesPage", () => {
  it("renders real contract rows with day counts", () => {
    render(
      <DeadlinesPage
        error={null}
        contracts={[
          {
            id: 1,
            contract_no: "C-2026-0001",
            title: "工事請負契約 A",
            counterparty: "テスト建設株式会社",
            contract_type: "工事請負契約",
            end_date: futureDate(10),
            amount: 5_000_000,
            status: "approved",
          },
        ]}
      />,
    );

    expect(screen.getByText("工事請負契約 A")).toBeInTheDocument();
    expect(screen.getByText("テスト建設株式会社")).toBeInTheDocument();
    expect(screen.getByText(/残 \d+ 日/)).toBeInTheDocument();
    expect(screen.getByText("5,000,000 円")).toBeInTheDocument();
  });

  it("marks expired contracts and shows empty state when no end dates", () => {
    render(
      <DeadlinesPage
        error={null}
        contracts={[
          {
            id: 2,
            contract_no: "C-2026-0002",
            title: "期限切れ契約",
            counterparty: "旧取引先",
            contract_type: "賃貸借契約",
            end_date: futureDate(-5),
            amount: null,
            status: "approved",
          },
        ]}
      />,
    );

    expect(screen.getAllByText("期限切れ").length).toBeGreaterThan(0);
  });

  it("shows error alert when load failed", () => {
    render(
      <DeadlinesPage
        error="契約データを取得できませんでした。時間をおいて再試行してください。"
        contracts={[]}
      />,
    );

    expect(
      screen.getByText("契約データを取得できませんでした。時間をおいて再試行してください。"),
    ).toBeInTheDocument();
  });
});
