import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import EvidencePage from "../page-client";

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
  evidenceApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    emailIngest: jest.fn(),
    get: jest.fn(),
    duplicates: jest.fn(),
    timeline: jest.fn(),
    viewHistory: jest.fn(),
    export: jest.fn(),
    custody: jest.fn(),
    addCustodyEvent: jest.fn(),
    linkLegalHold: jest.fn(),
    requestHoldRelease: jest.fn(),
    holdReleaseRequests: jest.fn(),
    decideHoldRelease: jest.fn(),
  },
}));

describe("EvidencePage", () => {
  it("renders the page heading", () => {
    render(<EvidencePage />);
    expect(screen.getByRole("heading", { name: "証拠管理" })).toBeInTheDocument();
  });

  it("offers the 証拠を登録 and メール証拠取込 buttons", () => {
    render(<EvidencePage />);
    expect(screen.getByRole("button", { name: /証拠を登録/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /メール証拠取込/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<EvidencePage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
