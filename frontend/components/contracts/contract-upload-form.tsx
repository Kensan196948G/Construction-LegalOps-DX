"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ContractUploadDropzone } from "@/components/features/contracts/contract-upload-dropzone";
import { CONTRACT_TYPES } from "@/lib/mock-data";

type Phase = "idle" | "uploading" | "reviewing" | "done";

export function ContractUploadForm() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [counterparty, setCounterparty] = useState("");
  const [contractType, setContractType] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");

  const canSubmit = files.length > 0 && counterparty.trim() && contractType && phase === "idle";

  const handleSubmit = () => {
    if (!canSubmit) return;
    setPhase("uploading");
    setTimeout(() => {
      setPhase("reviewing");
      setTimeout(() => {
        setPhase("done");
        setTimeout(() => {
          router.push("/reviews/REV-0001");
        }, 1500);
      }, 2200);
    }, 1200);
  };

  if (phase === "done") {
    return (
      <div className="flex flex-col items-center gap-4 py-10">
        <CheckCircle2 className="h-12 w-12 text-emerald-500" />
        <p className="text-lg font-semibold">AI レビューが完了しました</p>
        <p className="text-sm text-muted-foreground">レビュー詳細ページへ移動します…</p>
      </div>
    );
  }

  if (phase === "reviewing") {
    return (
      <div className="flex flex-col items-center gap-4 py-10">
        <Sparkles className="h-10 w-10 animate-pulse text-primary" />
        <p className="text-base font-semibold">AI 一次レビュー 実行中…</p>
        <p className="text-sm text-muted-foreground">
          契約条項の分析・リスク評価を行っています。しばらくお待ちください。
        </p>
        <div className="mt-2 flex gap-1">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="h-2 w-2 animate-bounce rounded-full bg-primary/60"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (phase === "uploading") {
    return (
      <div className="flex flex-col items-center gap-4 py-10">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-base font-semibold">アップロード中…</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <ContractUploadDropzone value={files} onChange={setFiles} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">相手方名称 *</label>
          <Input
            placeholder="例: 大成建設工業(株)"
            value={counterparty}
            onChange={e => setCounterparty(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">契約種別 *</label>
          <Select value={contractType} onValueChange={setContractType}>
            <SelectTrigger>
              <SelectValue placeholder="種別を選択" />
            </SelectTrigger>
            <SelectContent>
              {CONTRACT_TYPES.map(t => (
                <SelectItem key={t} value={t}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button onClick={handleSubmit} disabled={!canSubmit} className="w-full gap-2">
        <Sparkles className="h-4 w-4" />
        アップロードして AI レビューを開始
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        ※ AI レビュー結果は参考情報です。最終判断は法務担当者・顧問弁護士が行います。
      </p>
    </div>
  );
}
export default ContractUploadForm;
