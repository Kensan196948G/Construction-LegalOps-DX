"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  BookOpen,
  ExternalLink,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";

import { legalAiApi } from "@/lib/api/endpoints";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const SUGGESTED_QUESTIONS = [
  "下請法の支払期日（60日ルール）",
  "一括下請負の禁止と例外",
  "主任技術者・監理技術者の配置要件",
  "建設工事の契約書に必要な記載事項",
];

interface EvidenceHit {
  article_id: number;
  title: string;
  source_url?: string | null;
  excerpt: string;
  law_tags: string[];
  score: number;
  source_verified: boolean;
}

interface EvidenceResult {
  query: string;
  hits: EvidenceHit[];
  verifiedCount: number;
}

function HitCard({ hit }: { hit: EvidenceHit }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          {hit.source_verified ? (
            <Badge variant="default" className="gap-1">
              <BadgeCheck className="h-3 w-3" aria-hidden="true" />
              一次情報確認済み
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1">
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              要確認
            </Badge>
          )}
          {hit.law_tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
          <span className="ml-auto text-xs text-muted-foreground">
            関連度 {(hit.score * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-sm font-semibold">{hit.title}</p>
        <p className="text-sm text-muted-foreground leading-relaxed">{hit.excerpt}</p>
        {hit.source_url && (
          <a
            href={hit.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
            一次情報（国・自治体・公的機関）を開く
          </a>
        )}
      </CardContent>
    </Card>
  );
}

export default function ConsultationsPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvidenceResult | null>(null);

  const search = async (text: string) => {
    const q = text.trim();
    if (!q || loading) return;
    setQuery(text);
    setLoading(true);
    setError(null);
    try {
      const res = await legalAiApi.evidence({ query: q, limit: 8 });
      setResult({
        query: res.query,
        hits: res.hits,
        verifiedCount: res.hits.filter((h) => h.source_verified).length,
      });
    } catch {
      setError(
        "一次情報検索を実行できませんでした。時間をおいて再試行するか、法務担当者・顧問弁護士にご確認ください。",
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const hitCountLabel = useMemo(() => {
    if (!result) return null;
    return `${result.hits.length} 件の根拠資料（うち一次情報確認済み ${result.verifiedCount} 件）`;
  }, [result]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">法務相談</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          建設業法・下請法などの疑問を、国・自治体・公的機関の一次情報から検索します
        </p>
      </header>

      <Alert variant="default" className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>AI 出力は法的助言ではありません</AlertTitle>
        <AlertDescription>
          検索結果は参考情報であり、確定的な法的判断を示すものではありません。
          具体的な案件の判断は必ず法務担当者・顧問弁護士が行ってください。
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
            一次情報検索（根拠付き）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void search(query);
            }}
          >
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="例: 下請法の支払期日（60日ルール）"
              aria-label="検索キーワード"
              className="flex-1"
            />
            <Button type="submit" disabled={loading || !query.trim()} className="gap-2">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Search className="h-4 w-4" aria-hidden="true" />
              )}
              検索
            </Button>
          </form>

          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <Button
                key={q}
                variant="outline"
                size="sm"
                onClick={() => void search(q)}
                disabled={loading}
              >
                {q}
              </Button>
            ))}
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading && (
            <div className="space-y-3" aria-label="検索中">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          )}

          {!loading && result && result.hits.length === 0 && (
            <div className="rounded-md border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">
              <BookOpen className="mx-auto mb-2 h-8 w-8" aria-hidden="true" />
              該当する一次情報が見つかりませんでした。
              <br />
              検索語を変えるか、法務担当者・顧問弁護士にご相談ください。
            </div>
          )}

          {!loading && result && result.hits.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">{hitCountLabel}</p>
              {result.hits.map((hit) => (
                <HitCard key={hit.article_id} hit={hit} />
              ))}
            </div>
          )}

          {!loading && !result && !error && (
            <p className="text-sm text-muted-foreground">
              検索結果には根拠となる一次情報（国・自治体・公的機関の法令・ガイドライン等）へのリンクを表示します。
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
