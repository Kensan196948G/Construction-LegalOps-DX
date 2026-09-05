import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import LaborWagePage from "../page-client";

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
  laborWageApi: {
    standards: jest.fn().mockRejectedValue(new Error("offline")),
    createStandard: jest.fn(),
    latest: jest.fn(),
    discrepancy: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("LaborWagePage", () => {
  it("renders the page heading", () => {
    render(<LaborWagePage />);
    expect(screen.getByRole("heading", { name: "労務費基準" })).toBeInTheDocument();
  });

  it("offers the 基準値を登録 button", () => {
    render(<LaborWagePage />);
    expect(screen.getByRole("button", { name: /基準値を登録/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<LaborWagePage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
