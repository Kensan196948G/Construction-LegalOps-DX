import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/app-header";
import { Sidebar } from "@/components/layout/sidebar";
import { AiDisclaimerBanner } from "@/components/legal/ai-disclaimer-banner";

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
  return (
    <div className="flex min-h-screen bg-muted/20">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <AppHeader />
        <AiDisclaimerBanner
          message="AI は法的判断を確定しません。最終判断は法務担当者・顧問弁護士が行います"
          variant="global"
        />
        <main
          id="main-content"
          role="main"
          aria-label="メインコンテンツ"
          className="flex-1 px-6 py-6 lg:px-10"
        >
          {children}
        </main>
        <footer className="border-t bg-card px-6 py-3 text-xs text-muted-foreground lg:px-10">
          <div className="flex flex-col items-start justify-between gap-1 sm:flex-row sm:items-center">
            <p>
              &copy; {new Date().getFullYear()} Construction-LegalOps-DX —
              法務 DX 推進室
            </p>
            <p>
              本システムの AI 出力は参考情報であり、最終的な法的判断は
              <span className="font-medium"> 法務担当者・顧問弁護士 </span>
              が行います。
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
