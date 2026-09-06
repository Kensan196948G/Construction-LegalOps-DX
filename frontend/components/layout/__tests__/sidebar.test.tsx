import React from "react";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "../sidebar";

let mockPathname = "/dashboard";

jest.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

describe("Sidebar active item highlighting", () => {
  it("highlights only the most specific match for a nested path (N8 regression)", () => {
    mockPathname = "/compliance/antitrust";
    render(<Sidebar />);

    const antitrustLink = screen.getByRole("link", { name: /独禁法・入札談合/ });
    const complianceLink = screen.getByRole("link", { name: /コンプライアンスチェック/ });

    expect(antitrustLink).toHaveAttribute("aria-current", "page");
    expect(complianceLink).not.toHaveAttribute("aria-current");
  });

  it("highlights the parent item when on its own page", () => {
    mockPathname = "/compliance";
    render(<Sidebar />);

    const complianceLink = screen.getByRole("link", { name: /コンプライアンスチェック/ });
    const antitrustLink = screen.getByRole("link", { name: /独禁法・入札談合/ });

    expect(complianceLink).toHaveAttribute("aria-current", "page");
    expect(antitrustLink).not.toHaveAttribute("aria-current");
  });
});
