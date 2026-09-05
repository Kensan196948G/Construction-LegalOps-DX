import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import JvPage from "../page-client";

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
  jvApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    get: jest.fn(),
    setStatus: jest.fn(),
    members: jest.fn().mockRejectedValue(new Error("offline")),
    addMember: jest.fn(),
    agreements: jest.fn(),
    createAgreement: jest.fn(),
    disputes: jest.fn(),
    createDispute: jest.fn(),
    respondDispute: jest.fn(),
    settlements: jest.fn(),
    createSettlement: jest.fn(),
    settle: jest.fn(),
    dashboard: jest.fn().mockRejectedValue(new Error("offline")),
  },
  contractsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("JvPage", () => {
  it("renders the page heading", () => {
    render(<JvPage />);
    expect(screen.getByRole("heading", { name: "JV 管理" })).toBeInTheDocument();
  });

  it("offers the JV を登録 button", () => {
    render(<JvPage />);
    expect(screen.getByRole("button", { name: /JV を登録/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<JvPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
