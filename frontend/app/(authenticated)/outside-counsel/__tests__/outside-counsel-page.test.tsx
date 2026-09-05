import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import OutsideCounselPage from "../page-client";

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
  engagementsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    get: jest.fn(),
    create: jest.fn(),
    answer: jest.fn(),
    confirm: jest.fn(),
    cancel: jest.fn(),
  },
  lawFirmsApi: {
    list: jest.fn().mockRejectedValue(new Error("offline")),
    create: jest.fn(),
    lawyers: jest.fn().mockRejectedValue(new Error("offline")),
    createLawyer: jest.fn(),
  },
}));

describe("OutsideCounselPage", () => {
  it("renders the page heading", () => {
    render(<OutsideCounselPage />);
    expect(screen.getByRole("heading", { name: "顧問弁護士" })).toBeInTheDocument();
  });

  it("offers the 依頼を起票 button", () => {
    render(<OutsideCounselPage />);
    expect(screen.getByRole("button", { name: /依頼を起票/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<OutsideCounselPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });
});
