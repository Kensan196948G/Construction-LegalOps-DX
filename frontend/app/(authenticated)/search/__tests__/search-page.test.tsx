import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SearchPage from "../page-client";

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
  contractSearchApi: {
    search: jest.fn().mockRejectedValue(new Error("offline")),
  },
}));

describe("SearchPage", () => {
  it("renders the page heading and a search form", () => {
    render(<SearchPage />);
    expect(screen.getByRole("heading", { name: "契約検索" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /検索/ })).toBeInTheDocument();
    expect(screen.getByLabelText("検索キーワード")).toBeInTheDocument();
  });

  it("shows an offline error when search is submitted while API is down", async () => {
    render(<SearchPage />);
    fireEvent.change(screen.getByLabelText("検索キーワード"), {
      target: { value: "損害賠償" },
    });
    fireEvent.click(screen.getByRole("button", { name: /検索/ }));
    await waitFor(() => {
      expect(screen.getByText(/検索を実行できませんでした/)).toBeInTheDocument();
    });
  });
});
