/**
 * 日付フォーマッタ (date-fns + ja ロケール)
 */

import { format, formatDistanceToNow, parseISO } from "date-fns";
import { ja } from "date-fns/locale";

type DateLike = Date | string | number | null | undefined;

function toDate(input: DateLike): Date | null {
  if (input === null || input === undefined || input === "") return null;
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input;
  if (typeof input === "number") {
    const d = new Date(input);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  try {
    const d = parseISO(input);
    return Number.isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

/** "2026年5月16日" */
export function formatDate(input: DateLike, pattern = "yyyy年M月d日"): string {
  const d = toDate(input);
  if (!d) return "";
  return format(d, pattern, { locale: ja });
}

/** "2026年5月16日 12:34" */
export function formatDateTime(input: DateLike, pattern = "yyyy年M月d日 HH:mm"): string {
  const d = toDate(input);
  if (!d) return "";
  return format(d, pattern, { locale: ja });
}

/** "2026/05/16" (slash 区切り) */
export function formatDateSlash(input: DateLike): string {
  return formatDate(input, "yyyy/MM/dd");
}

/** "3 時間前" */
export function formatRelativeTime(input: DateLike): string {
  const d = toDate(input);
  if (!d) return "";
  return formatDistanceToNow(d, { addSuffix: true, locale: ja });
}

/** ISO 文字列を厳密に Date へ */
export function parseIsoDate(input: string): Date | null {
  return toDate(input);
}
