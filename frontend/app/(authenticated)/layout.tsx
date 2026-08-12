import type { Metadata } from "next";

import { AuthenticatedShell } from "@/components/layout/authenticated-shell";

export const metadata: Metadata = {
  title: {
    default: "ホーム",
    template: "%s | Construction-LegalOps-DX",
  },
};

/**
 * 認証済みエリア共通レイアウト。
 *
 * AI 免責バナーは **弁護士法第 72 条遵守** および
 * `docs/ai_disclaimer_policy.md` に基づき、認証済み全画面で常時表示する。
 * AI 生成結果が含まれる画面 (契約レビュー / リスク / コンプライアンス等) では、
 * 追加で画面内インラインの免責文も併記する想定。
 */
export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthenticatedShell>{children}</AuthenticatedShell>;
}
