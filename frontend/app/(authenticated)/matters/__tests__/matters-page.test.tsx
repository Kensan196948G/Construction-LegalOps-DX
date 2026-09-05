import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import MattersPage from "../page-client";

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
  mattersApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    setStatus: jest.fn(),
    assign: jest.fn(),
    linkContract: jest.fn(),
    unlinkContract: jest.fn(),
    contracts: jest.fn(),
    setLegalHold: jest.fn(),
    events: jest.fn(),
    addNote: jest.fn(),
  },
  usersApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("MattersPage", () => {
  it("renders the page heading", () => {
    render(<MattersPage />);
    expect(screen.getByRole("heading", { name: "法務案件" })).toBeInTheDocument();
  });

  it("offers the Matter 作成 button", () => {
    render(<MattersPage />);
    expect(screen.getByRole("button", { name: /Matter 作成/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<MattersPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
