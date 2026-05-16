type RiskLevel = "low" | "medium" | "high" | "critical";
interface Props {
  byLevel: Array<{ level: RiskLevel; count: number }>;
  byCategory: Array<{ category: string; count: number }>;
}

const LEVEL_LABEL: Record<RiskLevel, string> = { low: "低", medium: "中", high: "高", critical: "重大" };
const LEVEL_COLOR: Record<RiskLevel, string> = { low: "bg-emerald-500", medium: "bg-amber-400", high: "bg-orange-500", critical: "bg-red-600" };
const LEVEL_TEXT: Record<RiskLevel, string> = { low: "text-emerald-600", medium: "text-amber-600", high: "text-orange-600", critical: "text-red-600" };

export function RisksOverview({ byLevel, byCategory }: Props) {
  const maxLevel = Math.max(...byLevel.map(d => d.count), 1);
  const maxCat = Math.max(...byCategory.map(d => d.count), 1);
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">リスクレベル別</p>
        <div className="space-y-2">
          {byLevel.map(d => (
            <div key={d.level} className="flex items-center gap-3">
              <span className={`w-8 shrink-0 text-xs font-bold ${LEVEL_TEXT[d.level]}`}>{LEVEL_LABEL[d.level]}</span>
              <div className="flex-1 rounded-full bg-muted h-2">
                <div className={`${LEVEL_COLOR[d.level]} h-2 rounded-full`} style={{ width: `${(d.count / maxLevel) * 100}%` }} />
              </div>
              <span className="w-6 shrink-0 text-right text-sm font-semibold">{d.count}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">カテゴリ別</p>
        <div className="space-y-2">
          {byCategory.map(d => (
            <div key={d.category} className="flex items-center gap-3">
              <span className="w-28 shrink-0 truncate text-xs text-muted-foreground">{d.category}</span>
              <div className="flex-1 rounded-full bg-muted h-2">
                <div className="bg-primary h-2 rounded-full" style={{ width: `${(d.count / maxCat) * 100}%` }} />
              </div>
              <span className="w-6 shrink-0 text-right text-sm font-semibold">{d.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
export default RisksOverview;
