interface DistItem { level: "low" | "medium" | "high" | "critical"; count: number; }
interface Props { data: DistItem[]; }

const LABELS = { low: "低リスク", medium: "中リスク", high: "高リスク", critical: "重大リスク" };
const COLORS = { low: "bg-emerald-500", medium: "bg-amber-400", high: "bg-orange-500", critical: "bg-red-600" };

export function RiskDistributionChart({ data }: Props) {
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div className="space-y-3">
      {data.map(d => (
        <div key={d.level} className="flex items-center gap-3">
          <span className="w-20 shrink-0 text-xs text-muted-foreground">{LABELS[d.level]}</span>
          <div className="flex-1 rounded-full bg-muted h-2.5">
            <div className={`${COLORS[d.level]} h-2.5 rounded-full`} style={{ width: `${(d.count / max) * 100}%` }} />
          </div>
          <span className="w-6 shrink-0 text-right text-sm font-semibold">{d.count}</span>
        </div>
      ))}
    </div>
  );
}
export default RiskDistributionChart;
