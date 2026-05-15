/**
 * UI 表示用の補助マスキングユーティリティ。
 *
 * NOTE:
 *   個人情報・機微情報はサーバ側で必要なマスキング処理を行うことが原則。
 *   本ユーティリティはあくまでフロントエンド表示時の追加保護 (fallback) であり、
 *   サーバから値がそのまま返ってきた場合に最終防衛として適用する位置付け。
 */

/**
 * マイナンバー (12 桁) を頭 4 桁 + 末 4 桁 + 中央伏字で表示。
 *   例: "123456789012" → "1234 **** 9012"
 */
export function maskMyNumber(input: string | null | undefined): string {
  if (!input) return "";
  const digits = input.replace(/\D/g, "");
  if (digits.length !== 12) {
    // 12 桁でない場合は全体伏字に倒す (堅牢側に倒す)
    return digits.length ? "*".repeat(digits.length) : "";
  }
  return `${digits.slice(0, 4)} **** ${digits.slice(8, 12)}`;
}

/**
 * 電話番号 (日本) を国番号/局番のみ残す形でマスク。
 *   例: "03-1234-5678" → "03-****-5678"
 *       "09012345678"  → "090-****-5678"
 */
export function maskPhoneNumber(input: string | null | undefined): string {
  if (!input) return "";
  const digits = input.replace(/\D/g, "");
  if (digits.length < 6) return "*".repeat(digits.length);

  // 080/090/070 系 (11 桁)
  if (/^(080|090|070)/.test(digits) && digits.length === 11) {
    return `${digits.slice(0, 3)}-****-${digits.slice(7)}`;
  }
  // 03/06 系 (10 桁)
  if (/^0[36]/.test(digits) && digits.length === 10) {
    return `${digits.slice(0, 2)}-****-${digits.slice(6)}`;
  }
  // 一般 (10 桁)
  if (digits.length === 10) {
    return `${digits.slice(0, 3)}-****-${digits.slice(6)}`;
  }
  // フォールバック: 末尾 4 桁のみ残す
  return `${"*".repeat(digits.length - 4)}${digits.slice(-4)}`;
}

/**
 * メールアドレスのローカル部を一部マスキング。
 *   例: "yamada.taro@example.co.jp" → "y***@example.co.jp"
 */
export function maskEmail(input: string | null | undefined): string {
  if (!input) return "";
  const at = input.indexOf("@");
  if (at < 1) return "*".repeat(input.length);
  const local = input.slice(0, at);
  const domain = input.slice(at);
  if (local.length <= 1) return `${local}***${domain}`;
  return `${local[0]}***${domain}`;
}

/**
 * 銀行口座番号 (任意桁) を末尾 4 桁のみ残す。
 */
export function maskBankAccount(input: string | null | undefined): string {
  if (!input) return "";
  const digits = input.replace(/\D/g, "");
  if (digits.length <= 4) return "*".repeat(digits.length);
  return `${"*".repeat(digits.length - 4)}${digits.slice(-4)}`;
}

/**
 * 汎用 (末尾 keep 文字のみ残す)。
 */
export function maskTail(input: string | null | undefined, keep = 4, masker = "*"): string {
  if (!input) return "";
  if (input.length <= keep) return masker.repeat(input.length);
  return `${masker.repeat(input.length - keep)}${input.slice(-keep)}`;
}
