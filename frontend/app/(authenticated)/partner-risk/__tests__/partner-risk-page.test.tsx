import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import PartnerRiskPage from "../page-client";

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
  partnersApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
  },
  partnerExtApi: {
    alerts: jest.fn().mockRejectedValue(new Error("offline")),
    expiryFlags: jest.fn(),
    riskScore: jest.fn(),
    refreshRiskScore: jest.fn(),
    reviews: jest.fn(),
    createReview: jest.fn(),
    completeReview: jest.fn(),
  },
}));

describe("PartnerRiskPage", () => {
  it("renders the page heading", () => {
    render(<PartnerRiskPage />);
    expect(screen.getByRole("heading", { name: "協力会社リスク" })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<PartnerRiskPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
