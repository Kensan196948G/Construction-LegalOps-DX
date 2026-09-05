"use client";

import { useCallback, useState } from "react";
import { BookOpen, ExternalLink, Loader2, Search } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { contractSearchApi } from "@/lib/api";
import type { ContractSearchHit } from "@/lib/api/schemas";

const SCOPE_LABELS: Record<string, string> = {
  all: "すべて",
  contracts: "契約メタデータ",
  clauses: "条項",
  documents: "契約文書",
};

const KIND_LABELS: Record<string, string> = {
  contract: "契約",
  clause: "条項",
  document: "文書",
};

function HitRow({ hit }: { hit: ContractSearchHit }) {
  const target =
    hit.kind === "contract" ? `/contracts/${hit.contract_id}` : undefined;
  return (
    <div className="rounded-md border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{KIND_LABELS[hit.kind] ?? hit.kind}</Badge>
        <span className="text-sm font-semibold">{hit.title ?? "（タイトルなし）"}</span>
        <span className="ml-auto text-xs text-muted-foreground">
          関連度 {Math.round(hit.score * 100)}%
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {hit.contract_no ?? `契約 ID ${hit.contract_id}`}
        {hit.matched_fields.length > 0 && (
          <span className="ml-2">
            一致: {hit.matched_fields.map((f) => f.replace(/_/g, " ")).join(", ")}
          </span>
        )}
      </p>
      {hit.snippet && (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {hit.snippet}
        </p>
      )}
      {target && (
        <Link
          href={target}
          className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
          契約詳細を開く
        </Link>
      )}
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("all");
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hits, setHits] = useState<ContractSearchHit[]>([]);

  const runSearch = useCallback(
    async (text: string, scopeValue: string) => {
      const q = text.trim();
      if (!q || loading) return;
      setLoading(true);
      setSearched(false);
      setError(null);
      try {
        const result = await contractSearchApi.search({
          q,
          scope: scopeValue,
          limit: 50,
        });
        setHits(result);
        setSearched(true);
      } catch {
        setHits([]);
        setSearched(true);
        setError("検索を実行できませんでした。時間をおいて再試行してください。");
      } finally {
        setLoading(false);
      }
    },
    [loading]
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">契約検索</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          契約メタデータ・条項本文・契約文書を横断検索します（ヒット位置スニペット付き）
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4 text-primary" aria-hidden="true" />
            全文検索
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void runSearch(query, scope);
            }}
          >
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="例: 損害賠償 上限／瑕疵担保／秘密保持"
              aria-label="検索キーワード"
              className="flex-1"
            />
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger className="w-44" aria-label="検索対象">
                <SelectValue placeholder="対象" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(SCOPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={loading || !query.trim()} className="gap-2">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Search className="h-4 w-4" aria-hidden="true" />
              )}
              検索
            </Button>
          </form>

          {loading && (
            <div className="space-y-3" aria-label="検索中">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          )}

          {error && (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </p>
          )}

          {!loading && searched && !error && hits.length === 0 && (
            <div className="rounded-md border bg-muted/40 px-4 py-10 text-center text-sm text-muted-foreground">
              <BookOpen className="mx-auto mb-2 h-8 w-8" aria-hidden="true" />
              該当する契約が見つかりませんでした。
              <br />
              検索語を変えるか、対象範囲を広げてお試しください。
            </div>
          )}

          {!loading && searched && !error && hits.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{hits.length} 件のヒット</p>
              {hits.map((hit) => (
                <HitRow key={`${hit.kind}-${hit.record_id}`} hit={hit} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
