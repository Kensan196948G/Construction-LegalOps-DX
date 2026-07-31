import { toFindingStatus } from "@/lib/compliance/status";

describe("toFindingStatus", () => {
  it("maps missing severities to not_run instead of warning", () => {
    expect(toFindingStatus(null)).toBe("not_run");
    expect(toFindingStatus(undefined)).toBe("not_run");
    expect(toFindingStatus("")).toBe("not_run");
  });

  it("maps configured severities to finding statuses", () => {
    expect(toFindingStatus("medium")).toBe("warning");
    expect(toFindingStatus("high")).toBe("non_compliant");
    expect(toFindingStatus("critical")).toBe("non_compliant");
  });
});
