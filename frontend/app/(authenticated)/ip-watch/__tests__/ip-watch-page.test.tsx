import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import IpWatchPage from "../page-client";

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
  ipWatchTargetsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
    sync: jest.fn(),
  },
  ipWatchEventsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    markRead: jest.fn(),
  },
  ipDashboardApi: {
    get: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("IpWatchPage", () => {
  it("renders the page heading and mock fallback target rows when offline", async () => {
    render(<IpWatchPage />);

    expect(
      screen.getByRole("heading", { name: "競合出願ウォッチ" })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("さくら土木(株)")).toBeInTheDocument();
      expect(screen.getByText("(株)つばさ組")).toBeInTheDocument();
    });
  });

  it("offers the ウォッチ対象登録 button", () => {
    render(<IpWatchPage />);
    expect(
      screen.getByRole("button", { name: /ウォッチ対象登録/ })
    ).toBeInTheDocument();
  });
});
