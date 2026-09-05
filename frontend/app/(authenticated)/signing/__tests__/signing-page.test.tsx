import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import SigningPage from "../page-client";

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
  signingApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    get: jest.fn(),
    create: jest.fn(),
    events: jest.fn(),
    send: jest.fn(),
    consent: jest.fn(),
    view: jest.fn(),
    sign: jest.fn(),
    complete: jest.fn(),
    cancel: jest.fn(),
  },
  contractsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("SigningPage", () => {
  it("renders the page heading", () => {
    render(<SigningPage />);
    expect(screen.getByRole("heading", { name: "電子契約・署名" })).toBeInTheDocument();
  });

  it("offers the エンベロープ作成 button", () => {
    render(<SigningPage />);
    expect(screen.getByRole("button", { name: /エンベロープ作成/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<SigningPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
