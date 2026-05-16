import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const MOCK_CLAUSES = [
  { id: "c1", article: "第1条", title: "目的", text: "本契約は、受注者が発注者から委託された工事を施工することを目的として締結するものである。", issues: 0 },
  { id: "c2", article: "第3条", title: "契約金額および支払条件", text: "契約金額は別紙明細書に定める通りとする。支払いは、納品確認後90日以内に行うものとする。", issues: 1 },
  { id: "c3", article: "第5条", title: "工期", text: "工期は契約締結日より180日間とする。天候不順その他の事情により工期の延長が必要な場合は、協議の上決定するものとする。", issues: 1 },
  { id: "c4", article: "第7条", title: "解除条項", text: "甲は、いつでも本契約を解除することができる。ただし、解除による損害については乙が負担するものとする。", issues: 1 },
  { id: "c5", article: "第9条", title: "検査・引渡し", text: "工事完成後、発注者は7日以内に完成検査を行うものとする。", issues: 0 },
  { id: "c6", article: "第12条", title: "損害賠償", text: "当事者の一方が本契約に違反したことにより相手方に損害を与えた場合は、当該損害を賠償する義務を負う。", issues: 1 },
  { id: "c7", article: "第15条", title: "秘密保持", text: "本契約の当事者は、本契約に関して知り得た一切の情報を第三者に開示してはならない。", issues: 1 },
  { id: "c8", article: "第18条", title: "管轄裁判所", text: "本契約に関する紛争については、東京地方裁判所を第一審の専属的合意管轄裁判所とする。", issues: 0 },
];

interface Props { contractId: string; }

export function ContractClausesViewer({ contractId: _ }: Props) {
  return (
    <div className="space-y-3">
      {MOCK_CLAUSES.map(c => (
        <div key={c.id} className="rounded-md border p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              {c.issues > 0
                ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
              }
              <span className="text-sm font-semibold">{c.article} {c.title}</span>
            </div>
            {c.issues > 0 && (
              <Badge variant="secondary" className="shrink-0 text-xs">
                論点 {c.issues}
              </Badge>
            )}
          </div>
          <p className="mt-2 pl-6 text-xs leading-relaxed text-muted-foreground">{c.text}</p>
        </div>
      ))}
    </div>
  );
}
export default ContractClausesViewer;
