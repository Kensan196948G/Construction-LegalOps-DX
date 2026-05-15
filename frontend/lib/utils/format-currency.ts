/**
 * 通貨フォーマッタ — 日本円既定。
 */

type NumberLike = number | string | null | undefined;

function toNumber(input: NumberLike): number | null {
  if (input === null || input === undefined || input === "") return null;
  const n = typeof input === "number" ? input : Number(input);
  return Number.isFinite(n) ? n : null;
}

export interface CurrencyFormatOptions {
  currency?: string;
  locale?: string;
  /** 単位省略表示 ("億"/"万" 等の和風単位) を行うか */
  compact?: boolean;
  /** compact=true のとき有効桁。既定 3 */
  significantDigits?: number;
  /** null 時の代替表示 */
  fallback?: string;
}

/**
 * 標準: "¥1,234,567"
 *
 * compact=true のとき、桁数が大きい金額は和風単位を付与する。
 *  - 1.23 億円 / 4,567 万円 等
 */
export function formatCurrency(
  amount: NumberLike,
  opts: CurrencyFormatOptions = {},
): string {
  const {
    currency = "JPY",
    locale = "ja-JP",
    compact = false,
    significantDigits = 3,
    fallback = "—",
  } = opts;

  const n = toNumber(amount);
  if (n === null) return fallback;

  if (compact && currency === "JPY") {
    return formatJpyCompact(n, significantDigits);
  }

  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "JPY" ? 0 : 2,
  }).format(n);
}

function formatJpyCompact(n: number, sig: number): string {
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const round = (v: number) => {
    if (v === 0) return "0";
    const digits = Math.max(0, sig - Math.floor(Math.log10(v)) - 1);
    return v.toFixed(Math.min(digits, 4)).replace(/\.?0+$/, "");
  };
  if (abs >= 1_0000_0000_0000) {
    return `${sign}${round(abs / 1_0000_0000_0000)}兆円`;
  }
  if (abs >= 1_0000_0000) {
    return `${sign}${round(abs / 1_0000_0000)}億円`;
  }
  if (abs >= 10000) {
    return `${sign}${round(abs / 10000)}万円`;
  }
  return `${sign}${Math.round(abs)}円`;
}

/** "1,234,567" (記号なし整形のみ) */
export function formatNumber(value: NumberLike, locale = "ja-JP"): string {
  const n = toNumber(value);
  if (n === null) return "";
  return new Intl.NumberFormat(locale).format(n);
}
