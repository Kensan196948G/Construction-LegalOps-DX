import { Badge } from "@/components/ui/badge";

const ROUTE_LABELS: Record<string, { label: string; desc: string }> = {
  A1: { label: "ルート A1", desc: "法務担当 → 法務リード" },
  A2: { label: "ルート A2", desc: "法務担当 → 法務リード → 部門長 → 弁護士" },
  B1: { label: "ルート B1", desc: "法務担当 → 法務リード" },
  B2: { label: "ルート B2", desc: "法務担当 → 法務リード → 部門長" },
  C1: { label: "ルート C1", desc: "法務担当のみ" },
  C2: { label: "ルート C2", desc: "法務担当 → 管理職" },
  D1: { label: "ルート D1", desc: "法務担当 → 弁護士確認 必須" },
};

interface Props { route: string; }

export function RouteBadge({ route }: Props) {
  const cfg = ROUTE_LABELS[route];
  return (
    <span className="inline-flex flex-col gap-0.5">
      <Badge variant="outline" className="w-fit text-xs">{cfg?.label ?? route}</Badge>
      {cfg && <span className="text-xs text-muted-foreground">{cfg.desc}</span>}
    </span>
  );
}
export default RouteBadge;
