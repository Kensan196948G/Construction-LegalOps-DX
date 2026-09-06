import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import WhistleblowerPage from "../page-client";

jest.mock("@/hooks/use-users", () => ({
  useCurrentUser: jest.fn().mockReturnValue({ data: undefined }),
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return {
    ApiError: actual.ApiError,
    whistleblowerApi: {
      list: jest.fn().mockRejectedValue(new Error("offline")),
      get: jest.fn(),
      create: jest.fn(),
      getReporterProfile: jest.fn(),
      setStatus: jest.fn(),
      promoteToMatter: jest.fn(),
      aggregate: jest.fn(),
      listAccess: jest.fn(),
      grantAccess: jest.fn(),
      revokeAccess: jest.fn(),
      listEvidence: jest.fn(),
      addEvidence: jest.fn(),
      listInterviews: jest.fn(),
      addInterview: jest.fn(),
      listTimeline: jest.fn(),
      addNote: jest.fn(),
      listActions: jest.fn(),
      addAction: jest.fn(),
      updateActionStatus: jest.fn(),
    },
  };
});

describe("WhistleblowerPage", () => {
  it("renders the page heading", () => {
    render(<WhistleblowerPage />);
    expect(screen.getByRole("heading", { name: "内部通報・調査" })).toBeInTheDocument();
  });

  it("offers the 通報を登録 button", () => {
    render(<WhistleblowerPage />);
    expect(screen.getByRole("button", { name: /通報を登録/ })).toBeInTheDocument();
  });

  it("shows an offline alert when the API is down", async () => {
    render(<WhistleblowerPage />);
    await waitFor(() => {
      expect(screen.getByText(/データを取得できませんでした/)).toBeInTheDocument();
    });
  });

  it("shows the reporter-identity isolation notice", () => {
    render(<WhistleblowerPage />);
    expect(
      screen.getByText(/通報者を特定できる情報は、案件ごとに付与された調査担当者/),
    ).toBeInTheDocument();
  });

  it("does not show the aggregate button for non-privileged roles", () => {
    render(<WhistleblowerPage />);
    expect(screen.queryByRole("button", { name: /経営報告匿名集計/ })).not.toBeInTheDocument();
  });
});
