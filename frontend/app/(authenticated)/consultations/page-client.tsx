"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, User, AlertTriangle, MessageSquareText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/lib/utils";

type Role = "system" | "user" | "ai";
interface Message { role: Role; text: string; timestamp?: string; }

// Simulated AI responses for common legal questions
const AI_RESPONSES: Record<string, string> = {
  default: "ご質問ありがとうございます。建設業法・下請法の観点から回答いたします。\n\n具体的な契約書の内容や案件の詳細によって判断が異なりますので、最終的な法的判断は必ず顧問弁護士にご確認ください。\n\n※ この回答は AI による参考情報です。法的助言を構成するものではありません。",
  下請法: "下請法（下請代金支払遅延等防止法）の主要なポイントをご説明します。\n\n【支払期日】第2条の4により、下請代金の支払期日は物品等の受領日から60日以内と定められています。これを超える支払期日の設定は違反となります。\n\n【書面の交付義務】第3条により、発注の際に必要事項を記載した書面（3条書面）を交付することが義務付けられています。\n\n【禁止事項】受領拒否・返品・代金の減額・不当に低い下請代金の設定などが禁止されています。\n\n※ この回答は AI による参考情報です。具体的な判断は顧問弁護士にご確認ください。",
  一括下請: "建設業法第22条の一括下請負の禁止についてご説明します。\n\n【原則】請負った建設工事を、一括して他の業者に請け負わせることは禁止されています。\n\n【例外】発注者が書面で承諾した場合は認められます（民間工事に限る）。\n\n【判断基準】元請業者が施工に実質的に関与しているか（施工計画の作成、品質管理、安全管理、工程管理等）が重要な判断基準です。\n\n※ この回答は AI による参考情報です。具体的な判断は顧問弁護士にご確認ください。",
  主任技術者: "建設業法第26条の技術者配置要件についてご説明します。\n\n【主任技術者】すべての建設工事現場に配置が必要です。\n\n【監理技術者】特定建設業者が4,000万円以上（建築一式は8,000万円以上）の下請契約を締結する場合に必要です。\n\n【専任要件】工事1件の請負代金が4,000万円以上（建築一式は8,000万円以上）の場合、専任の技術者が必要です。\n\n配置届の未提出は建設業法違反となりますのでご注意ください。\n\n※ この回答は AI による参考情報です。具体的な判断は顧問弁護士にご確認ください。",
  契約書: "建設工事の契約書面に関する規定（建設業法第19条）についてご説明します。\n\n【必須記載事項】工事内容、請負代金額、工事着手・完成時期、請負代金の支払方法、工事変更・損害の処理方法、不可抗力の処理方法、価格等の変動に伴う変更等について書面に記載が必要です。\n\n【電子書面】電磁的方法（電子書面）での交付も、相手方の承諾を得た上で認められています。\n\n【口頭契約】口頭のみの契約は建設業法違反となります。\n\n※ この回答は AI による参考情報です。具体的な判断は顧問弁護士にご確認ください。",
};

const SUGGESTED_QUESTIONS = [
  "下請法の支払期日（60日ルール）について教えてください",
  "一括下請負の禁止と例外について教えてください",
  "主任技術者・監理技術者の配置要件を確認したい",
  "建設工事の契約書に必要な記載事項は何ですか",
];

function getAiResponse(text: string): string {
  if (text.includes("下請法") || text.includes("支払")) return AI_RESPONSES.下請法;
  if (text.includes("一括") || text.includes("下請負")) return AI_RESPONSES.一括下請;
  if (text.includes("主任技術者") || text.includes("監理技術者") || text.includes("配置")) return AI_RESPONSES.主任技術者;
  if (text.includes("契約書") || text.includes("書面") || text.includes("記載")) return AI_RESPONSES.契約書;
  return AI_RESPONSES.default;
}

function now() {
  return new Date().toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
}

export default function ConsultationsPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "system",
      text: "法務相談 AI アシスタントです。建設業法・下請法・労働安全衛生法などに関するご質問にお答えします。\n\n回答はすべて参考情報であり、法的助言ではありません。具体的な案件については必ず顧問弁護士にご確認ください。",
    },
  ]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = (text?: string) => {
    const q = text ?? query;
    if (!q.trim() || loading) return;
    setMessages(m => [...m, { role: "user", text: q, timestamp: now() }]);
    setQuery("");
    setLoading(true);
    setTimeout(() => {
      setMessages(m => [...m, { role: "ai", text: getAiResponse(q), timestamp: now() }]);
      setLoading(false);
    }, 1800);
  };

  return (
    <div className="flex flex-col space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-foreground">法務相談</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI アシスタントによる建設業法務 Q&A（参考情報）
        </p>
      </header>

      {/* AI Disclaimer */}
      <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300" />
        <p>
          <strong>AI 出力は法的助言ではありません。</strong>
          回答は参考情報であり、確定的な法的判断を示すものではありません。具体的な案件の判断は必ず法務担当者・顧問弁護士が行ってください。
        </p>
      </div>

      {/* Chat card */}
      <Card className="flex flex-col overflow-hidden">
        <CardContent className="flex flex-col overflow-hidden p-0">
          {/* Messages */}
          <div className="h-[420px] overflow-y-auto p-4 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
                {/* Avatar */}
                <div className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                  m.role === "system" && "bg-muted text-muted-foreground",
                  m.role === "ai" && "bg-primary text-primary-foreground",
                  m.role === "user" && "bg-blue-600 text-white"
                )}>
                  {m.role === "ai" && <Sparkles className="h-4 w-4" />}
                  {m.role === "user" && <User className="h-4 w-4" />}
                  {m.role === "system" && <MessageSquareText className="h-4 w-4" />}
                </div>

                {/* Bubble */}
                <div className={cn("max-w-[75%] space-y-1", m.role === "user" && "items-end")}>
                  {m.role === "ai" && (
                    <Badge variant="secondary" className="gap-1 text-xs">
                      <Sparkles className="h-3 w-3" /> AI 参考情報
                    </Badge>
                  )}
                  <div className={cn(
                    "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                    m.role === "user" && "rounded-tr-sm bg-blue-600 text-white",
                    m.role === "ai" && "rounded-tl-sm bg-muted text-foreground",
                    m.role === "system" && "rounded-tl-sm border bg-card text-muted-foreground italic"
                  )}>
                    <p style={{ whiteSpace: "pre-wrap" }}>{m.text}</p>
                  </div>
                  {m.timestamp && (
                    <p className={cn("text-xs text-muted-foreground", m.role === "user" && "text-right")}>
                      {m.timestamp}
                    </p>
                  )}
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
                  <div className="flex gap-1">
                    {[0, 1, 2].map(i => (
                      <div
                        key={i}
                        className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggested questions */}
          {messages.length <= 1 && (
            <div className="border-t px-4 py-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">よくある質問</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map(q => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="rounded-full border bg-background px-3 py-1.5 text-xs text-foreground hover:bg-accent transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="border-t p-4">
            <div className="flex gap-2">
              <Input
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
                placeholder="法務に関する質問を入力... (Enter で送信)"
                disabled={loading}
                className="flex-1"
              />
              <Button
                onClick={() => send()}
                disabled={loading || !query.trim()}
                size="default"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              AI の回答は参考情報です。最終判断は法務担当者・顧問弁護士が行います。
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
