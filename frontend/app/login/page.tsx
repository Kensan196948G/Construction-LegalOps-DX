import type { Metadata } from "next";
import Image from "next/image";

import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = {
  title: "ログイン",
  description: "Construction-LegalOps-DX にサインインします。",
};

interface LoginPageProps {
  searchParams?: Promise<{
    callbackUrl?: string;
    error?: string;
  }>;
}

/**
 * 未認証ランディング。
 * - Entra ID (Microsoft) SSO を主、メール/パスワードを補助として `LoginForm` (Components Team) が描画。
 * - middleware が未認証アクセスを `/login?callbackUrl=...` に redirect する想定。
 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = (await searchParams) ?? {};
  const callbackUrl = params.callbackUrl ?? "/dashboard";
  const error = params.error;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Image
            src="/logo.svg"
            alt="Construction-LegalOps-DX"
            width={56}
            height={56}
            priority
          />
          <h1 className="mt-4 text-2xl font-bold text-foreground">
            Construction-LegalOps-DX
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            建設業向け 法務 DX プラットフォーム
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">ログイン</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            会社の Microsoft アカウントでサインインしてください。
          </p>

          <div className="mt-6">
            <LoginForm callbackUrl={callbackUrl} error={error} />
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          本システムの利用には法務部の許可が必要です。アクセス権限に関する
          ご質問は、システム管理者までお問い合わせください。
        </p>
      </div>
    </main>
  );
}
