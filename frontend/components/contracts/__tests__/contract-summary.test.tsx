import React from "react";
import { render, screen } from "@testing-library/react";
import { ContractSummary } from "../contract-summary";

const BASE_CONTRACT = {
  id: "c1",
  title: "工事請負契約テスト",
  counterparty: "株式会社テスト建設",
  contractType: "工事請負契約",
  amount: 12000000,
  currency: "JPY",
  startDate: "2026-04-01",
  endDate: "2027-03-31",
  status: "approved",
  riskLevel: "low",
  summary: "本契約はテスト用の工事請負契約です。",
};

describe("ContractSummary", () => {
  it("renders contract type", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("工事請負契約")).toBeInTheDocument();
  });

  it("renders counterparty name", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("株式会社テスト建設")).toBeInTheDocument();
  });

  it("renders formatted amount", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText(/¥12,000,000|¥12.000.000/)).toBeInTheDocument();
  });

  it("renders em dash for null amount", () => {
    render(<ContractSummary contract={{ ...BASE_CONTRACT, amount: null }} />);
    // Multiple em dashes may exist (startDate/endDate could also be null) — just check presence
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("renders start and end dates", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("2026-04-01")).toBeInTheDocument();
    expect(screen.getByText("2027-03-31")).toBeInTheDocument();
  });

  it("renders em dash for null dates", () => {
    render(<ContractSummary contract={{ ...BASE_CONTRACT, startDate: null, endDate: null }} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("renders status badge with Japanese label", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("承認済み")).toBeInTheDocument();
  });

  it("renders summary text when provided", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("本契約はテスト用の工事請負契約です。")).toBeInTheDocument();
  });

  it("does not render summary block when summary is empty", () => {
    render(<ContractSummary contract={{ ...BASE_CONTRACT, summary: "" }} />);
    expect(screen.queryByText(/本契約/)).not.toBeInTheDocument();
  });

  it("renders label headers for each field", () => {
    render(<ContractSummary contract={BASE_CONTRACT} />);
    expect(screen.getByText("状態")).toBeInTheDocument();
    expect(screen.getByText("契約種別")).toBeInTheDocument();
    expect(screen.getByText("相手方")).toBeInTheDocument();
    expect(screen.getByText("契約金額")).toBeInTheDocument();
    expect(screen.getByText("開始日")).toBeInTheDocument();
    expect(screen.getByText("終了日")).toBeInTheDocument();
  });
});
