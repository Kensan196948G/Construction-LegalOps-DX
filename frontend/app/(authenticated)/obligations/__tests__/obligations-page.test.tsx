import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import ObligationsPage from "../page-client";

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
  obligationsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    renewalCheck: jest.fn().mockRejectedValue(new Error("offline")),
    update: jest.fn(),
    complete: jest.fn(),
    waive: jest.fn(),
    createForContract: jest.fn(),
  },
  contractsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("ObligationsPage", () => {
  it("renders the page heading", () => {
    render(<ObligationsPage />);
    expect(screen.getByRole("heading", { name: "契約義務" })).toBeInTheDocument();
  });

  it("offers the 義務を登録 button", () => {
    render(<ObligationsPage />);
    expect(screen.getByRole("button", { name: /義務を登録/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<ObligationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
