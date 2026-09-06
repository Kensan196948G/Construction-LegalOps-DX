import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import AntitrustCompliancePage from "../page-client";

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
  antitrustApi: {
    listChecks: jest.fn().mockRejectedValue(new Error("offline")),
    getCheck: jest.fn(),
    runCheck: jest.fn(),
    listApplications: jest.fn().mockRejectedValue(new Error("offline")),
    getApplication: jest.fn(),
    createApplication: jest.fn(),
    decideApplication: jest.fn(),
    completeApplication: jest.fn(),
    cancelApplication: jest.fn(),
    listConsultations: jest.fn().mockRejectedValue(new Error("offline")),
    consult: jest.fn(),
    listTrainings: jest.fn().mockRejectedValue(new Error("offline")),
    createTraining: jest.fn(),
  },
}));

describe("AntitrustCompliancePage", () => {
  it("renders the page heading", () => {
    render(<AntitrustCompliancePage />);
    expect(
      screen.getByRole("heading", { name: /独禁法・入札談合コンプライアンス/ }),
    ).toBeInTheDocument();
  });

  it("shows the four tabs", () => {
    render(<AntitrustCompliancePage />);
    expect(screen.getByRole("tab", { name: "チェック実行" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "事前申請" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "AI 相談" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "研修履歴" })).toBeInTheDocument();
  });

  it("offers the チェックを実行 button", () => {
    render(<AntitrustCompliancePage />);
    expect(screen.getByRole("button", { name: /チェックを実行/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<AntitrustCompliancePage />);
    await waitFor(() => {
      expect(screen.getByText(/チェック結果を取得できませんでした/)).toBeInTheDocument();
    });
  });
});
