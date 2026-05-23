import { Fragment } from "react";

type RiskLevel = "low" | "medium" | "high" | "critical";
interface HeatmapCell {
  probability: 1 | 2 | 3 | 4;
  impact: 1 | 2 | 3 | 4;
  count: number;
}
interface Props {
  byLevel: Array<{ level: RiskLevel; count: number }>;
  byCategory: Array<{ category: string; count: number }>;
  heatmapData?: HeatmapCell[];
}

const LEVEL_LABEL: Record<RiskLevel, string> = { low: "低", medium: "中", high: "高", critical: "重大" };
const LEVEL_COLOR: Record<RiskLevel, string> = { low: "bg-emerald-500", medium: "bg-amber-400", high: "bg-orange-500", critical: "bg-red-600" };
const LEVEL_TEXT: Record<RiskLevel, string> = { low: "text-emerald-600", medium: "text-amber-600", high: "text-orange-600", critical: "text-red-600" };

function heatmapCellColor(probability: number, impact: number): string {
  const score = probability * impact;
  if (score >= 13) return "bg-red-500 text-white";
  if (score >= 9) return "bg-orange-400 text-white";
  if (score >= 5) return "bg-amber-300 text-amber-900";
  return "bg-emerald-200 text-emerald-900";
}

const PROB_LABELS: Record<number, string> = { 4: "高 (4)", 3: "中高 (3)", 2: "低中 (2)", 1: "低 (1)" };
const IMP_LABELS: Record<number, string> = { 1: "軽微", 2: "小", 3: "中", 4: "大" };

export function RisksOverview({ byLevel, byCategory, heatmapData }: Props) {
  const maxLevel = Math.max(...byLevel.map(d => d.count), 1);
  const maxCat = Math.max(...byCategory.map(d => d.count), 1);

  const getCount = (p: number, i: number): number =>
    heatmapData?.find(c => c.probability === p && c.impact === i)?.count ?? 0;

  return (
    <div className="space-y-6">
      {/* 4×4 Heatmap */}
      {heatmapData && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            リスクマトリクス（発生可能性 × 影響度）
          </p>
          <div className="flex gap-2">
            {/* Y-axis label */}
            <div className="flex items-center justify-center">
              <span
                className="text-xs text-muted-foreground font-medium"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                発生可能性
              </span>
            </div>
            <div className="flex-1">
              {/* Grid rows: probability 4→1 (top to bottom) */}
              <div className="grid gap-1" style={{ gridTemplateColumns: "auto 1fr 1fr 1fr 1fr" }}>
                {([4, 3, 2, 1] as const).map(p => (
                  <Fragment key={p}>
                    <div className="flex items-center justify-end pr-2">
                      <span className="text-xs text-muted-foreground whitespace-nowrap">{PROB_LABELS[p]}</span>
                    </div>
                    {([1, 2, 3, 4] as const).map(i => {
                      const count = getCount(p, i);
                      return (
                        <div
                          key={`${p}-${i}`}
                          className={`rounded flex flex-col items-center justify-center min-h-[52px] ${heatmapCellColor(p, i)}`}
                        >
                          <span className="text-lg font-bold leading-none">{count}</span>
                          {count > 0 && <span className="text-[10px] opacity-70 mt-0.5">件</span>}
                        </div>
                      );
                    })}
                  </Fragment>
                ))}
                {/* X-axis labels */}
                <div />
                {([1, 2, 3, 4] as const).map(i => (
                  <div key={`imp-${i}`} className="text-center">
                    <span className="text-xs text-muted-foreground">{IMP_LABELS[i]}</span>
                  </div>
                ))}
              </div>
              {/* X-axis overall label */}
              <p className="mt-1 text-center text-xs text-muted-foreground">影響度</p>
            </div>
          </div>
          {/* Legend */}
          <div className="mt-3 flex flex-wrap gap-3">
            {[
              { label: "低 (1–4)", cls: "bg-emerald-200" },
              { label: "中 (5–8)", cls: "bg-amber-300" },
              { label: "高 (9–12)", cls: "bg-orange-400" },
              { label: "重大 (13–16)", cls: "bg-red-500" },
            ].map(({ label, cls }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className={`h-3 w-3 rounded ${cls}`} />
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bar charts */}
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
    </div>
  );
}
export default RisksOverview;
