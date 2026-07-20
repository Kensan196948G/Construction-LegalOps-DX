"use client";

import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/lib/api/client";
import { useCreateTemplate } from "@/hooks/use-templates";

const CONTRACT_TYPES = ["請負", "委託", "共同企業体", "秘密保持", "覚書"] as const;

function slugify(input: string) {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.detail ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "ひな形を作成できませんでした。入力内容と接続状態を確認してください。";
}

export function CreateTemplateButton({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [contractType, setContractType] = useState<string>(CONTRACT_TYPES[0]);
  const [body, setBody] = useState("");

  const suggestedCode = useMemo(() => slugify(name), [name]);
  const createTemplate = useCreateTemplate({
    onSuccess: template => {
      toast({
        title: "ひな形を作成しました",
        description: `${template.name} を一覧に追加しました。`,
      });
      setOpen(false);
      setName("");
      setCode("");
      setContractType(CONTRACT_TYPES[0]);
      setBody("");
      router.refresh();
    },
    onError: error => {
      toast({
        title: "ひな形を作成できません",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    },
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const finalCode = (code.trim() || suggestedCode).trim();
    const finalName = name.trim();
    const finalBody = body.trim();

    if (!finalName || !finalCode) {
      toast({
        title: "必須項目を入力してください",
        description: "ひな形名とコードは必須です。",
        variant: "destructive",
      });
      return;
    }

    createTemplate.mutate({
      code: finalCode,
      name: finalName,
      contract_type: contractType,
      body: finalBody || undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>新規ひな形を作成</DialogTitle>
            <DialogDescription>
              契約種別、管理コード、ひな形本文を登録します。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="template-name">ひな形名</Label>
              <Input
                id="template-name"
                value={name}
                onChange={event => setName(event.target.value)}
                placeholder="工事請負契約ひな形"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-code">コード</Label>
              <Input
                id="template-code"
                value={code}
                onChange={event => setCode(slugify(event.target.value))}
                placeholder={suggestedCode || "construction-contract"}
                required={!suggestedCode}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="template-contract-type">契約種別</Label>
            <Select value={contractType} onValueChange={setContractType}>
              <SelectTrigger id="template-contract-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CONTRACT_TYPES.map(type => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="template-body">本文</Label>
            <Textarea
              id="template-body"
              value={body}
              onChange={event => setBody(event.target.value)}
              placeholder="契約条項、確認事項、添付書類の指示などを入力"
              className="min-h-40"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={createTemplate.isPending}
            >
              キャンセル
            </Button>
            <Button type="submit" disabled={createTemplate.isPending}>
              {createTemplate.isPending ? "作成中" : "作成"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default CreateTemplateButton;
