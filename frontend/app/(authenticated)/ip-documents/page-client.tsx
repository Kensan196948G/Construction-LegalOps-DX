"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, FileText, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ipAssetsApi, ipDocumentsApi } from "@/lib/api";
import type { IpAsset, IpDocument } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const DOC_TYPE_LABELS: Record<string, string> = {
  refusal_reason: "拒絶理由通知書",
  opinion_amendment: "意見書・手続補正書",
  decision: "発送書類（査定等）",
  citation: "引用文献情報",
};

interface DocRow {
  id: string;
  application_number: string;
  invention_title: string;
  doc_type: string;
  doc_name: string;
  fetched_at: string;
  analyzed: boolean;
  ai_summary: string | null;
  ai_findings: IpDocument["ai_findings"];
}

function toRow(asset: IpAsset, doc: IpDocument): DocRow {
  return {
    id: String(doc.id),
    application_number: asset.application_number,
    invention_title: asset.invention_title ?? "",
    doc_type: doc.doc_type,
    doc_name: doc.doc_name ?? DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type,
    fetched_at: doc.fetched_at,
    analyzed: Boolean(doc.analyzed_at),
    ai_summary: doc.ai_summary ?? null,
    ai_findings: doc.ai_findings ?? {},
  };
}

export default function IpDocumentsPage() {
  const [rows, setRows] = useState<DocRow[]>([]);
  const [assets, setAssets] = useState<IpAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const [assetFilter, setAssetFilter] = useState("all");
  const [selected, setSelected] = useState<DocRow | null>(null);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);
  const [fetchingAssetId, setFetchingAssetId] = useState<string | number | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const assetsRes = await ipAssetsApi.list({ page: 1, size: 100 });
      setAssets(assetsRes.items);
      const docs: DocRow[] = [];
      for (const asset of assetsRes.items) {
        const assetDocs = await ipAssetsApi.documents(asset.id);
        for (const d of assetDocs) docs.push(toRow(asset, d));
      }
      setRows(docs);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (typeFilter !== "all" && r.doc_type !== typeFilter) return false;
      if (assetFilter !== "all" && r.application_number !== assetFilter) return false;
      return true;
    });
  }, [rows, typeFilter, assetFilter]);

  const fetchForAsset = async (asset: IpAsset) => {
    setFetchingAssetId(asset.id);
    try {
      const result = await ipAssetsApi.fetchDocuments(asset.id, [
        "refusal_reason",
        "opinion_amendment",
        "decision",
        "citation",
      ]);
      await load();
      setMessage(
        `${asset.application_number}: ${result.fetched.length} 件の書類を収集しました` +
          (result.errors.length ? `（エラー ${result.errors.length} 件）` : "")
      );
      setTimeout(() => setMessage(""), 6000);
    } catch {
      setOffline(true);
    } finally {
      setFetchingAssetId(null);
    }
  };

  const analyze = async (row: DocRow) => {
    setBusyDocId(row.id);
    try {
      const result = await ipDocumentsApi.analyze(row.id);
      setSelected({
        ...row,
        analyzed: true,
        ai_summary: result.summary,
        ai_findings: result.findings as IpDocument["ai_findings"],
      });
      setRows((prev) =>
        prev.map((r) =>
          r.id === row.id
            ? {
                ...r,
                analyzed: true,
                ai_summary: result.summary,
                ai_findings: result.findings as IpDocument["ai_findings"],
              }
            : r
        )
      );
    } catch {
      setOffline(true);
    } finally {
      setBusyDocId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">審査書類の収集・AI解析</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            拒絶理由通知書・意見書などの審査書類を JPO API から収集し、AI で要約・論点・期限を解析します
          </p>
        </div>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          オフライン表示（API に接続できません）
        </Badge>
      )}
      {message && (
        <Badge variant="outline" className="border-emerald-400 bg-emerald-50 text-emerald-800 dark:bg-emerald-950">
          {message}
        </Badge>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">書類収集</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted-foreground">
            収集元の出願を選択して書類を取得します（拒絶理由通知書・意見書・発送書類・引用文献の 4 種）
          </p>
          <div className="flex flex-wrap gap-2">
            {assets.length === 0 && (
              <p className="text-sm text-muted-foreground">
                知財台帳に出願がありません。先に「知財台帳」から出願を登録してください
              </p>
            )}
            {assets.map((asset) => (
              <Button
                key={asset.id}
                variant="outline"
                size="sm"
                onClick={() => void fetchForAsset(asset)}
                disabled={fetchingAssetId === asset.id}
              >
                <Download className={`mr-1 h-3 w-3 ${fetchingAssetId === asset.id ? "animate-pulse" : ""}`} />
                {asset.application_number}
                {asset.invention_title ? `（${asset.invention_title.slice(0, 20)}）` : ""}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">書類一覧</CardTitle>
            <div className="flex gap-2">
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="書類種別" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全種別</SelectItem>
                  <SelectItem value="refusal_reason">拒絶理由通知書</SelectItem>
                  <SelectItem value="opinion_amendment">意見書・手続補正書</SelectItem>
                  <SelectItem value="decision">発送書類（査定等）</SelectItem>
                  <SelectItem value="citation">引用文献情報</SelectItem>
                </SelectContent>
              </Select>
              <Select value={assetFilter} onValueChange={setAssetFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="出願" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全出願</SelectItem>
                  {assets.map((a) => (
                    <SelectItem key={a.id} value={a.application_number}>
                      {a.application_number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>出願番号</TableHead>
                <TableHead>書類名</TableHead>
                <TableHead>収集日時</TableHead>
                <TableHead>AI 解析</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.application_number}</TableCell>
                  <TableCell>
                    <button
                      className="text-left font-medium hover:underline"
                      onClick={() => setSelected(r)}
                    >
                      {r.doc_name}
                    </button>
                  </TableCell>
                  <TableCell className="text-xs">
                    {new Date(r.fetched_at).toLocaleString("ja-JP")}
                  </TableCell>
                  <TableCell>
                    {r.analyzed ? (
                      <Badge variant="default">解析済</Badge>
                    ) : (
                      <Badge variant="outline">未解析</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void analyze(r)}
                      disabled={busyDocId === r.id}
                    >
                      <Sparkles className={`mr-1 h-3 w-3 ${busyDocId === r.id ? "animate-pulse" : ""}`} />
                      {r.analyzed ? "再解析" : "AI 解析"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                    {loading ? "読み込み中…" : "書類がありません。上のボタンから書類を収集してください"}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* 詳細ダイアログ */}
      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selected?.doc_name}</DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-mono text-xs text-muted-foreground">
                  {selected.application_number}
                </span>
                <span className="text-muted-foreground">{selected.invention_title}</span>
                {selected.analyzed && <Badge variant="default">AI 解析済</Badge>}
              </div>

              {selected.ai_summary ? (
                <div className="space-y-3">
                  <div className="rounded-md border bg-muted/30 p-3">
                    <p className="mb-1 flex items-center gap-1 text-sm font-semibold">
                      <Sparkles className="h-3.5 w-3.5" /> AI 要約
                    </p>
                    <p className="text-sm">{selected.ai_summary}</p>
                  </div>
                  {selected.ai_findings.issues?.length > 0 && (
                    <div>
                      <p className="mb-1 text-sm font-semibold">論点</p>
                      <ul className="space-y-2">
                        {selected.ai_findings.issues.map((issue, i) => (
                          <li key={i} className="rounded-md border p-2 text-sm">
                            <div className="flex items-center gap-2">
                              <Badge
                                variant={
                                  issue.severity === "high"
                                    ? "destructive"
                                    : issue.severity === "medium"
                                      ? "default"
                                      : "outline"
                                }
                              >
                                {issue.severity}
                              </Badge>
                              <span className="font-medium">{issue.title}</span>
                            </div>
                            {issue.description && (
                              <p className="mt-1 text-muted-foreground">{issue.description}</p>
                            )}
                            {issue.law && <p className="mt-0.5 text-xs">{issue.law}</p>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selected.ai_findings.deadline && (
                    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950">
                      <p className="font-semibold">期限</p>
                      <p>{selected.ai_findings.deadline}</p>
                    </div>
                  )}
                  {selected.ai_findings.suggested_actions?.length > 0 && (
                    <div>
                      <p className="mb-1 text-sm font-semibold">対応方針（候補）</p>
                      <ul className="list-disc pl-5 text-sm">
                        {selected.ai_findings.suggested_actions.map((action, i) => (
                          <li key={i}>{action}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selected.ai_findings.disclaimer && (
                    <p className="text-xs text-muted-foreground">{selected.ai_findings.disclaimer}</p>
                  )}
                </div>
              ) : (
                <div className="rounded-md border bg-muted/30 p-4 text-center">
                  <FileText className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    まだ AI 解析されていません。「AI 解析」ボタンで解析を実行できます
                  </p>
                </div>
              )}

              <div>
                <p className="mb-1 text-sm font-semibold">原文テキスト</p>
                <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border bg-muted/30 p-3 text-xs">
                  {selected.ai_findings ? "(テキストは書類詳細で確認できます)" : ""}
                </pre>
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <Button variant="outline" onClick={() => setSelected(null)}>
              閉じる
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
