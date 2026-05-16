const ROUTES = [
  { id: "A1", label: "ルート A1", steps: ["法務担当", "法務リード"], condition: "一般契約（3,000万円未満）", counsel: false },
  { id: "A2", label: "ルート A2", steps: ["法務担当", "法務リード", "部門長", "顧問弁護士"], condition: "高リスク契約・重要取引先", counsel: true },
  { id: "B1", label: "ルート B1", steps: ["法務担当", "法務リード"], condition: "資材購入（5,000万円未満）", counsel: false },
  { id: "B2", label: "ルート B2", steps: ["法務担当", "法務リード", "部門長"], condition: "資材購入（5,000万円以上）", counsel: false },
  { id: "C1", label: "ルート C1", steps: ["法務担当"], condition: "NDA・簡易契約", counsel: false },
  { id: "C2", label: "ルート C2", steps: ["法務担当", "管理職"], condition: "NDA（大企業相手）", counsel: false },
  { id: "D1", label: "ルート D1", steps: ["法務担当", "顧問弁護士"], condition: "紛争関連・法的リスク高", counsel: true },
];

export function WorkflowSettingsPanel() {
  return (
    <div className="space-y-3">
      {ROUTES.map(r => (
        <div key={r.id} className="rounded-md border p-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold">{r.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{r.condition}</p>
            </div>
            {r.counsel && (
              <span className="shrink-0 rounded bg-amber-100 dark:bg-amber-950 px-2 py-0.5 text-xs font-medium text-amber-800 dark:text-amber-200">
                弁護士確認 必須
              </span>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {r.steps.map((step, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium">{step}</span>
                {i < r.steps.length - 1 && <span className="text-muted-foreground text-xs">→</span>}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
export default WorkflowSettingsPanel;
