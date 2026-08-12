"use client";

import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toaster";
import { useUpdateContract } from "@/hooks/use-contracts";
import type { ApiError } from "@/lib/api";
import { CONTRACT_TYPES } from "@/lib/mock-data";
import type { Contract } from "@/lib/api/schemas";

const editSchema = z
  .object({
    title: z.string().min(1, "タイトルは必須です"),
    counterparty: z.string().min(1, "相手方は必須です"),
    contract_type: z.string().min(1, "契約種別は必須です"),
    amount: z
      .preprocess(
        (v) => (v === "" || v === null || v === undefined ? undefined : v),
        z.coerce.number().min(0, "金額は0以上にしてください").optional(),
      ),
    currency: z.string().length(3).default("JPY"),
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "日付は YYYY-MM-DD 形式です").nullable().optional(),
    end_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "日付は YYYY-MM-DD 形式です").nullable().optional(),
    confidentiality: z.enum(["public", "normal", "confidential", "strict"]).default("normal"),
    is_public_work: z.boolean().default(false),
    order_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "日付は YYYY-MM-DD 形式です").nullable().optional(),
    transaction_kind: z
      .enum(["construction", "manufacturing", "repair", "information", "service", "transport"])
      .nullable()
      .optional(),
  })
  .refine(
    (v) =>
      !v.start_date ||
      !v.end_date ||
      v.start_date <= v.end_date,
    { message: "開始日は終了日以前にしてください", path: ["end_date"] },
  );

type EditFormValues = z.infer<typeof editSchema>;

const CONFIDENTIALITY_LABELS: Record<string, string> = {
  public: "公開",
  normal: "一般",
  confidential: "社外秘",
  strict: "極秘",
};

const TRANSACTION_KIND_LABELS: Record<string, string> = {
  construction: "建設工事",
  manufacturing: "製造",
  repair: "修理",
  information: "情報",
  service: "役務",
  transport: "運送",
};

function toDateInput(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 10);
}

export function ContractEditForm({ contract }: { contract: Contract }) {
  const router = useRouter();
  const update = useUpdateContract({
    onSuccess: () => {
      toast({
        title: "保存しました",
        description: "契約情報を更新しました。監査ログに記録されます。",
      });
      router.push(`/contracts/${contract.id}`);
      router.refresh();
    },
    onError: (err) => {
      const apiError = err as ApiError;
      toast({
        title: "保存できませんでした",
        description:
          apiError.status === 409
            ? "他のユーザーが更新した可能性があります。最新の状態を再読込してから再度保存してください。"
            : apiError.message ?? "時間をおいて再試行してください。",
        variant: "destructive",
      });
    },
  });

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      title: contract.title,
      counterparty: contract.counterparty ?? "",
      contract_type: contract.contract_type,
      amount: contract.amount ?? undefined,
      currency: contract.currency ?? "JPY",
      start_date: toDateInput(contract.start_date),
      end_date: toDateInput(contract.end_date),
      confidentiality: contract.confidentiality ?? "normal",
      is_public_work: Boolean(contract.metadata?.is_public_work),
      order_date: toDateInput(
        typeof contract.metadata?.order_date === "string" ? contract.metadata.order_date : null,
      ),
      transaction_kind: null,
    },
  });

  const onSubmit = (values: EditFormValues) => {
    update.mutate({
      id: contract.id,
      data: {
        title: values.title,
        counterparty: values.counterparty,
        contract_type: values.contract_type,
        amount: values.amount === undefined || values.amount === null ? undefined : values.amount,
        currency: values.currency,
        start_date: values.start_date || undefined,
        end_date: values.end_date || undefined,
        confidentiality: values.confidentiality,
        version: contract.version ?? 1,
      },
    });
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="title">契約名 *</Label>
        <Input id="title" {...register("title")} />
        {errors.title && (
          <p className="text-xs text-destructive">{errors.title.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="counterparty">相手方名称 *</Label>
        <Input id="counterparty" {...register("counterparty")} />
        {errors.counterparty && (
          <p className="text-xs text-destructive">{errors.counterparty.message}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="contract_type">契約種別 *</Label>
          <Controller
            control={control}
            name="contract_type"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="contract_type" aria-label="契約種別">
                  <SelectValue placeholder="種別を選択" />
                </SelectTrigger>
                <SelectContent>
                  {CONTRACT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.contract_type && (
            <p className="text-xs text-destructive">{errors.contract_type.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="amount">契約金額（円）</Label>
          <Input
            id="amount"
            type="number"
            min={0}
            step="1"
            placeholder="例: 12000000"
            {...register("amount")}
          />
          {errors.amount && (
            <p className="text-xs text-destructive">{errors.amount.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="start_date">開始日</Label>
          <Input id="start_date" type="date" {...register("start_date")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="end_date">終了日</Label>
          <Input id="end_date" type="date" {...register("end_date")} />
          {errors.end_date && (
            <p className="text-xs text-destructive">{errors.end_date.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="confidentiality">機密区分</Label>
          <Controller
            control={control}
            name="confidentiality"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="confidentiality" aria-label="機密区分">
                  <SelectValue placeholder="区分を選択" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CONFIDENTIALITY_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="order_date">発注日</Label>
          <Input id="order_date" type="date" {...register("order_date")} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="currency">通貨</Label>
          <Controller
            control={control}
            name="currency"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="currency" aria-label="通貨">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="JPY">JPY（円）</SelectItem>
                  <SelectItem value="USD">USD（米ドル）</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="transaction_kind">取引区分</Label>
          <Controller
            control={control}
            name="transaction_kind"
            render={({ field }) => (
              <Select
                value={field.value ?? ""}
                onValueChange={(v) => field.onChange(v || null)}
              >
                <SelectTrigger id="transaction_kind" aria-label="取引区分">
                  <SelectValue placeholder="選択なし" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(TRANSACTION_KIND_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="is_public_work"
          type="checkbox"
          className="h-4 w-4 rounded border-input accent-primary"
          {...register("is_public_work")}
        />
        <Label htmlFor="is_public_work" className="font-normal">
          公共工事（国・自治体発注）
        </Label>
      </div>

      <div className="flex items-center justify-end gap-3 border-t pt-4">
        <Button type="button" variant="outline" onClick={() => router.back()}>
          キャンセル
        </Button>
        <Button type="submit" disabled={isSubmitting} className="gap-2">
          {isSubmitting ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Save className="h-4 w-4" aria-hidden="true" />
          )}
          保存
        </Button>
      </div>
    </form>
  );
}

export default ContractEditForm;
