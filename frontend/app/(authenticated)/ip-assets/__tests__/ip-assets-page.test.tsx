import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import IpAssetsPage from "../page-client";

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
  ipAssetsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
    sync: jest.fn(),
    documents: jest.fn(),
    fetchDocuments: jest.fn(),
  },
  ipDashboardApi: {
    get: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("IpAssetsPage", () => {
  it("renders the page heading and mock fallback rows when offline", async () => {
    render(<IpAssetsPage />);

    expect(
      screen.getByRole("heading", { name: "知財台帳" })
    ).toBeInTheDocument();

    await waitFor(() => {
      // デモ出願番号がモックフォールバックで表示される
      expect(screen.getByText("2026000001")).toBeInTheDocument();
      expect(screen.getByText("建設現場の安全管理システム（デモ）")).toBeInTheDocument();
      expect(screen.getByText("オフライン表示（モックデータ）")).toBeInTheDocument();
    });
  });

  it("offers the 出願登録 button", () => {
    render(<IpAssetsPage />);
    expect(
      screen.getByRole("button", { name: /出願登録/ })
    ).toBeInTheDocument();
  });
});
