import { Fragment } from "react";

type RiskLevel = "low" | "medium" | "high" | "critical";
/**
 * ヒートマップの 2 軸（発生可能性・影響度）の目盛り。
 *
 * DB の CHECK 制約（`ck_risk_probability` / `ck_risk_impact`）が
 * `low|medium|high` のため 3 段。backend の `RiskHeatmapCell` も
 * `RiskProbability` / `RiskImpact` で検証しており `critical` は返らない。
 * 4 段目を描画すると「重大リスク 0 件」に見えてしまうため 3×3 に合わせる。
 */
type HeatmapAxis = 1 | 2 | 3;
interface HeatmapCell {
  probability: HeatmapAxis;
  impact: HeatmapAxis;
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

/** スコア（1–9）の 3 バンド。低 1–3 / 中 4–6 / 高 7–9。 */
function heatmapCellColor(probability: number, impact: number): string {
  const score = probability * impact;
  if (score >= 7) return "bg-orange-400 text-white";
  if (score >= 4) return "bg-amber-300 text-amber-900";
  return "bg-emerald-200 text-emerald-900";
}

const PROB_LABELS: Record<HeatmapAxis, string> = { 3: "高", 2: "中", 1: "低" };
const IMP_LABELS: Record<HeatmapAxis, string> = { 1: "小", 2: "中", 3: "大" };

export function RisksOverview({ byLevel, byCategory, heatmapData }: Props) {
  const maxLevel = Math.max(...byLevel.map(d => d.count), 1);
  const maxCat = Math.max(...byCategory.map(d => d.count), 1);

  const getCount = (p: number, i: number): number =>
    heatmapData?.find(c => c.probability === p && c.impact === i)?.count ?? 0;

  return (
    <div className="space-y-6">
      {/* 3×3 Heatmap（発生可能性 low/medium/high × 影響度 low/medium/high） */}
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
              {/* Grid rows: probability 3→1 (top to bottom) */}
              <div className="grid gap-1" style={{ gridTemplateColumns: "auto 1fr 1fr 1fr" }}>
                {([3, 2, 1] as const).map(p => (
                  <Fragment key={p}>
                    <div className="flex items-center justify-end pr-2">
                      <span className="text-xs text-muted-foreground whitespace-nowrap">{PROB_LABELS[p]}</span>
                    </div>
                    {([1, 2, 3] as const).map(i => {
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
                {([1, 2, 3] as const).map(i => (
                  <div key={`imp-${i}`} className="text-center">
                    <span className="text-xs text-muted-foreground">{IMP_LABELS[i]}</span>
                  </div>
                ))}
              </div>
              {/* X-axis overall label */}
              <p className="mt-1 text-center text-xs text-muted-foreground">影響度</p>
            </div>
          </div>
          {/* Legend（到達可能なのは 3×3=9 まで） */}
          <div className="mt-3 flex flex-wrap gap-3">
            {[
              { label: "低 (1–3)", cls: "bg-emerald-200" },
              { label: "中 (4–6)", cls: "bg-amber-300" },
              { label: "高 (7–9)", cls: "bg-orange-400" },
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
