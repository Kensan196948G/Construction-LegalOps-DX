import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import NegotiationsPage from "../page-client";

jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>;
  MockLink.displayName = "MockLink";
  return MockLink;
});

jest.mock("@/lib/api", () => ({
  contractsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    clauses: jest.fn().mockRejectedValue(new Error("offline")),
  },
  negotiationsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    add: jest.fn(),
    setClauseStatus: jest.fn(),
    setClauseOwner: jest.fn(),
  },
}));

describe("NegotiationsPage", () => {
  it("renders the page heading", () => {
    render(<NegotiationsPage />);
    expect(screen.getByRole("heading", { name: "契約交渉・Redline" })).toBeInTheDocument();
  });

  it("asks the user to select a contract when none is preselected", async () => {
    render(<NegotiationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/交渉対象の契約を選択してください/)).toBeInTheDocument();
    });
  });

  it("shows an offline alert when the API is down", async () => {
    render(<NegotiationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
