"use client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Download, Copy } from "lucide-react";

type TStatus = "draft" | "published" | "archived";
interface TItem { id: string; title: string; contractType: string; version: string; status: TStatus; updatedBy: string; updatedAt: string; }
interface Props { items: TItem[]; total: number; page: number; perPage: number; }

const STATUS_LABEL: Record<TStatus, string> = { draft: "下書き", published: "公開中", archived: "アーカイブ" };
const STATUS_V: Record<TStatus, "secondary" | "default" | "outline"> = { draft: "secondary", published: "default", archived: "outline" };

export function TemplatesGrid({ items, total }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">ひな形が見つかりません</p>;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">{total} 件</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(t => (
          <Card key={t.id} className="flex flex-col hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
                <Badge variant={STATUS_V[t.status]} className="text-xs shrink-0">{STATUS_LABEL[t.status]}</Badge>
              </div>
              <CardTitle className="text-sm leading-snug mt-2">{t.title}</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 pb-2">
              <div className="space-y-1 text-xs text-muted-foreground">
                <p>種別: {t.contractType}</p>
                <p>バージョン: <span className="font-mono">{t.version}</span></p>
                <p>更新: {t.updatedAt} by {t.updatedBy}</p>
              </div>
            </CardContent>
            <CardFooter className="gap-2 pt-2">
              <Button variant="outline" size="sm" className="flex-1 gap-1">
                <Download className="h-3.5 w-3.5" />ダウンロード
              </Button>
              <Button variant="ghost" size="sm" className="gap-1">
                <Copy className="h-3.5 w-3.5" />複製
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
export default TemplatesGrid;
