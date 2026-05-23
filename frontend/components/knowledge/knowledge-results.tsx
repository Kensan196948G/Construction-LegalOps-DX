import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, Scale, HelpCircle, BookOpen } from "lucide-react";

type KSource = "internal_doc" | "precedent" | "faq" | "playbook";
interface KItem { id: string; title: string; excerpt: string; source: KSource; category: string; tags: string[]; updatedAt: string; score: number; }
interface Props { items: KItem[]; total: number; page: number; perPage: number; }

const SOURCE_LABEL: Record<KSource, string> = { internal_doc: "社内文書", precedent: "判例", faq: "FAQ", playbook: "プレイブック" };
const SOURCE_ICON: Record<KSource, React.ComponentType<{ className?: string }>> = { internal_doc: FileText, precedent: Scale, faq: HelpCircle, playbook: BookOpen };
const SOURCE_V: Record<KSource, "default" | "secondary" | "outline"> = { internal_doc: "default", precedent: "secondary", faq: "outline", playbook: "secondary" };

export function KnowledgeResults({ items, total }: Props) {
  if (!items.length) return <div className="py-16 text-center text-sm text-muted-foreground">キーワードを入力するか、カテゴリを選択してください</div>;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">{total} 件のナレッジが見つかりました</p>
      {items.map(k => {
        const Icon = SOURCE_ICON[k.source];
        return (
          <Card key={k.id} className="hover:shadow-sm transition-shadow">
            <CardContent className="pt-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0">
                    <h3 className="font-medium leading-snug hover:underline cursor-pointer">{k.title}</h3>
                    <p className="mt-1.5 text-sm text-muted-foreground line-clamp-2">{k.excerpt}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge variant={SOURCE_V[k.source]} className="text-xs">{SOURCE_LABEL[k.source]}</Badge>
                      <Badge variant="outline" className="text-xs">{k.category}</Badge>
                      {k.tags.map(t => <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{t}</span>)}
                    </div>
                  </div>
                </div>
                <p className="shrink-0 text-xs text-muted-foreground">{k.updatedAt}</p>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
export default KnowledgeResults;
