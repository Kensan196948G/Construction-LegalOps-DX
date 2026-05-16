import { Badge } from "@/components/ui/badge";

type RiskLevel = "low" | "medium" | "high" | "critical";

const RISK_LABEL: Record<RiskLevel, string> = {
  low: "低リスク", medium: "中リスク", high: "高リスク", critical: "重大リスク",
};
const RISK_CLASS: Record<RiskLevel, string> = {
  low: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950 dark:text-amber-200",
  high: "bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-950 dark:text-orange-200",
  critical: "bg-red-100 text-red-800 border-red-200 dark:bg-red-950 dark:text-red-200",
};

interface Props { level: RiskLevel; }

export function RiskBadge({ level }: Props) {
  return (
    <Badge variant="outline" className={RISK_CLASS[level]}>
      {RISK_LABEL[level]}
    </Badge>
  );
}
export default RiskBadge;
