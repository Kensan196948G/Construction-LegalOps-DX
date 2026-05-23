import React from "react";
import { render, screen } from "@testing-library/react";
import { ContractsTable } from "../contracts-table";

// next/link renders as <a> in jest jsdom
jest.mock("next/link", () => {
  const MockLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

const BASE_ITEM = {
  id: "c1",
  title: "工事請負契約 A",
  counterparty: "株式会社テスト建設",
  contractType: "工事請負契約",
  amount: 5000000,
  status: "approved",
  riskLevel: "low" as const,
  updatedAt: "2026-05-01",
};

describe("ContractsTable", () => {
  it("shows empty message when items array is empty", () => {
    render(<ContractsTable items={[]} total={0} page={1} perPage={20} />);
    expect(screen.getByText("契約が見つかりません")).toBeInTheDocument();
  });

  it("renders a contract row with title link", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={1} page={1} perPage={20} />);
    const link = screen.getByRole("link", { name: "工事請負契約 A" });
    expect(link).toHaveAttribute("href", "/contracts/c1");
  });

  it("renders status badge with correct label", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={1} page={1} perPage={20} />);
    expect(screen.getByText("承認済み")).toBeInTheDocument();
  });

  it("renders risk badge with correct label", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={1} page={1} perPage={20} />);
    expect(screen.getByText("低")).toBeInTheDocument();
  });

  it("formats amount as Japanese yen", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={1} page={1} perPage={20} />);
    expect(screen.getByText(/¥5,000,000|¥5.000.000/)).toBeInTheDocument();
  });

  it("shows em dash for null amount", () => {
    const item = { ...BASE_ITEM, amount: null };
    render(<ContractsTable items={[item]} total={1} page={1} perPage={20} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows pagination when totalPages > 1", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={50} page={1} perPage={20} />);
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
    expect(screen.getByText("次へ")).toBeInTheDocument();
  });

  it("hides pagination when only one page", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={1} page={1} perPage={20} />);
    expect(screen.queryByText("前へ")).not.toBeInTheDocument();
    expect(screen.queryByText("次へ")).not.toBeInTheDocument();
  });

  it("shows display range label", () => {
    render(<ContractsTable items={[BASE_ITEM]} total={25} page={1} perPage={20} />);
    expect(screen.getByText(/25 件中/)).toBeInTheDocument();
  });

  it("renders multiple rows", () => {
    const items = [
      BASE_ITEM,
      { ...BASE_ITEM, id: "c2", title: "業務委託契約 B", status: "in_review", riskLevel: "high" as const },
    ];
    render(<ContractsTable items={items} total={2} page={1} perPage={20} />);
    expect(screen.getByText("工事請負契約 A")).toBeInTheDocument();
    expect(screen.getByText("業務委託契約 B")).toBeInTheDocument();
  });
});
