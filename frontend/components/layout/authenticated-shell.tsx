"use client";

import { useState } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { Sidebar } from "@/components/layout/sidebar";
import { AiDisclaimerBanner } from "@/components/legal/ai-disclaimer-banner";

export function AuthenticatedShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/20">
      <Sidebar className="hidden lg:flex" />
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          aria-hidden="true"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <Sidebar
        className={`fixed inset-y-0 left-0 z-50 lg:hidden ${mobileOpen ? "flex" : "hidden"}`}
      />

      <div className="flex min-h-screen flex-1 flex-col">
        <AppHeader onMenuClick={() => setMobileOpen((v) => !v)} />
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

export default AuthenticatedShell;
