import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface Framework { id: string; label: string; passed: number; failed: number; na: number; }
interface Props { frameworks: Framework[]; }

export function ComplianceChecklist({ frameworks }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {frameworks.map(f => {
        const total = f.passed + f.failed + f.na;
        const rate = total > 0 ? Math.round((f.passed / total) * 100) : 0;
        return (
          <div key={f.id} className="rounded-lg border p-4 space-y-3">
            <p className="text-sm font-semibold leading-tight">{f.label}</p>
            <div className="flex items-end justify-between">
              <span className="text-2xl font-bold">{rate}%</span>
              <span className="text-xs text-muted-foreground">適合率</span>
            </div>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${rate}%` }} />
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-0.5 text-emerald-600">
                <CheckCircle2 className="h-3 w-3" />{f.passed}件
              </span>
              <span className="flex items-center gap-0.5 text-amber-600">
                <AlertTriangle className="h-3 w-3" />{f.na}件
              </span>
              <span className="flex items-center gap-0.5 text-destructive">
                <XCircle className="h-3 w-3" />{f.failed}件
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
export default ComplianceChecklist;
