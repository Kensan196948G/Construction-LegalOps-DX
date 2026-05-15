/**
 * リスクレベル → Tailwind カラー / ラベルマッピング。
 *
 * ベースカラーは Tailwind の標準パレットを利用 (custom palette が無くても効くよう)。
 */

import type { RiskLevel } from "@/lib/api/schemas";

export interface RiskVisual {
  /** バッジ向けクラス (背景 + 文字色 + 境界) */
  badgeClassName: string;
  /** テキストのみ用クラス */
  textClassName: string;
  /** 背景のみ (チャート等用) */
  bgClassName: string;
  /** ヒートマップセル用 (薄い背景) */
  cellClassName: string;
  /** 表示ラベル (日本語) */
  label: string;
  /** RGB hex (recharts 等で文字列カラーが必要な箇所向け) */
  hex: string;
}

const TABLE: Record<RiskLevel, RiskVisual> = {
  low: {
    badgeClassName:
      "bg-emerald-50 text-emerald-700 border border-emerald-200",
    textClassName: "text-emerald-700",
    bgClassName: "bg-emerald-500",
    cellClassName: "bg-emerald-100 text-emerald-900",
    label: "低",
    hex: "#10b981",
  },
  medium: {
    badgeClassName: "bg-amber-50 text-amber-700 border border-amber-200",
    textClassName: "text-amber-700",
    bgClassName: "bg-amber-500",
    cellClassName: "bg-amber-100 text-amber-900",
    label: "中",
    hex: "#f59e0b",
  },
  high: {
    badgeClassName: "bg-orange-50 text-orange-700 border border-orange-200",
    textClassName: "text-orange-700",
    bgClassName: "bg-orange-500",
    cellClassName: "bg-orange-100 text-orange-900",
    label: "高",
    hex: "#f97316",
  },
  critical: {
    badgeClassName: "bg-red-50 text-red-700 border border-red-300",
    textClassName: "text-red-700",
    bgClassName: "bg-red-600",
    cellClassName: "bg-red-100 text-red-900",
    label: "重大",
    hex: "#dc2626",
  },
};

/** 未知のレベルも安全に処理するためのフォールバック。 */
const FALLBACK: RiskVisual = {
  badgeClassName: "bg-slate-50 text-slate-700 border border-slate-200",
  textClassName: "text-slate-700",
  bgClassName: "bg-slate-400",
  cellClassName: "bg-slate-100 text-slate-900",
  label: "—",
  hex: "#94a3b8",
};

export function getRiskVisual(level: RiskLevel | string | null | undefined): RiskVisual {
  if (!level) return FALLBACK;
  return TABLE[level as RiskLevel] ?? FALLBACK;
}

export function getRiskColor(level: RiskLevel | string | null | undefined): string {
  return getRiskVisual(level).hex;
}

export function getRiskBadgeClass(level: RiskLevel | string | null | undefined): string {
  return getRiskVisual(level).badgeClassName;
}

export function getRiskLabel(level: RiskLevel | string | null | undefined): string {
  return getRiskVisual(level).label;
}
