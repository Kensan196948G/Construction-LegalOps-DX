import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import PublicWorksPage from "../page-client";

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
  },
  contractingAgenciesApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
  },
  ownerNotificationsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    notify: jest.fn(),
    cancel: jest.fn(),
  },
  publicWorksConsultationsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    respond: jest.fn(),
    cancel: jest.fn(),
  },
  publicWorksApi: {
    standardClauseCheck: jest.fn().mockRejectedValue(new Error("offline")),
    dashboard: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("PublicWorksPage", () => {
  it("renders the page heading", () => {
    render(<PublicWorksPage />);
    expect(screen.getByRole("heading", { name: "公共工事" })).toBeInTheDocument();
  });

  it("offers the 協議を申出 button", () => {
    render(<PublicWorksPage />);
    expect(screen.getByRole("button", { name: /協議を申出/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<PublicWorksPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
