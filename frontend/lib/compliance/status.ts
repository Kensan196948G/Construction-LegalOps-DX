export type ComplianceFindingStatus = "compliant" | "warning" | "non_compliant" | "not_run";

export function toFindingStatus(severity: string | null | undefined): ComplianceFindingStatus {
  if (severity === null || severity === undefined || severity === "") return "not_run";
  if (severity === "high" || severity === "critical") return "non_compliant";
  if (severity === "medium") return "warning";
  return "warning";
}
