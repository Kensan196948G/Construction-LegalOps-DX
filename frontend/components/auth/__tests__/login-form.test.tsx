import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

import { LoginForm } from "../login-form";

const signInMock = jest.fn(() => Promise.resolve(undefined));

jest.mock("next-auth/react", () => ({
  signIn: (...args: unknown[]) => signInMock(...args),
}));

describe("LoginForm (Cloudflare Access)", () => {
  beforeEach(() => {
    signInMock.mockClear();
  });

  it("auto-triggers cloudflare-access sign-in when behind Access", async () => {
    render(<LoginForm callbackUrl="/dashboard" behindAccess />);

    await waitFor(() => {
      expect(signInMock).toHaveBeenCalledWith("cloudflare-access", {
        callbackUrl: "/dashboard",
      });
    });
    expect(screen.getByRole("status")).toHaveTextContent("サインインしています");
  });

  it("does NOT sign in and shows guidance when not behind Access", () => {
    render(<LoginForm callbackUrl="/dashboard" behindAccess={false} />);

    expect(signInMock).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Cloudflare Access.*リンク経由でサインイン/s),
    ).toBeInTheDocument();
  });

  it("renders a retry action when a prior sign-in errored", () => {
    render(<LoginForm callbackUrl="/" behindAccess error="AccessSignInFailed" />);

    // The auto-signin effect is suppressed while an error is shown.
    expect(signInMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "再試行" })).toBeInTheDocument();
  });
});
