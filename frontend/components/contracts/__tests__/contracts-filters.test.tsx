import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ContractsFilters } from "../contracts-filters";

const mockPush = jest.fn();
const mockPathname = "/contracts";
const mockSearchParams = new URLSearchParams();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

beforeEach(() => {
  mockPush.mockClear();
});

describe("ContractsFilters", () => {
  it("renders search input", () => {
    render(<ContractsFilters defaultValues={{}} />);
    expect(screen.getByPlaceholderText("契約名・取引先を検索")).toBeInTheDocument();
  });

  it("renders status select trigger", () => {
    render(<ContractsFilters defaultValues={{}} />);
    expect(screen.getByText("ステータス")).toBeInTheDocument();
  });

  it("renders contract type select trigger", () => {
    render(<ContractsFilters defaultValues={{}} />);
    expect(screen.getByText("契約種別")).toBeInTheDocument();
  });

  it("renders risk level select trigger", () => {
    render(<ContractsFilters defaultValues={{}} />);
    expect(screen.getByText("リスク")).toBeInTheDocument();
  });

  it("does not show clear button when no filters active", () => {
    render(<ContractsFilters defaultValues={{}} />);
    expect(screen.queryByText("クリア")).not.toBeInTheDocument();
  });

  it("shows clear button when a filter is active", () => {
    render(<ContractsFilters defaultValues={{ q: "テスト" }} />);
    expect(screen.getByText("クリア")).toBeInTheDocument();
  });

  it("calls router.push with pathname on clear", () => {
    render(<ContractsFilters defaultValues={{ status: "approved" }} />);
    fireEvent.click(screen.getByText("クリア"));
    expect(mockPush).toHaveBeenCalledWith(mockPathname);
  });

  it("calls router.push when search input changes", () => {
    render(<ContractsFilters defaultValues={{}} />);
    const input = screen.getByPlaceholderText("契約名・取引先を検索");
    fireEvent.change(input, { target: { value: "工事" } });
    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("q=%E5%B7%A5%E4%BA%8B"));
  });

  it("prefills search input from defaultValues", () => {
    render(<ContractsFilters defaultValues={{ q: "既存検索" }} />);
    const input = screen.getByPlaceholderText("契約名・取引先を検索") as HTMLInputElement;
    expect(input.defaultValue).toBe("既存検索");
  });
});
