import type { Metadata } from "next";
import { headers } from "next/headers";
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
 *
 * 本デプロイの認証境界は Cloudflare Access。エッジで認証済みのリクエストには
 * `Cf-Access-Authenticated-User-Email` が付与されるため、その場合は
 * `LoginForm` が `cloudflare-access` provider へ自動サインインする。
 * middleware が未認証アクセスを `/login?callbackUrl=...` に redirect する。
 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = (await searchParams) ?? {};
  const callbackUrl = params.callbackUrl ?? "/dashboard";
  const error = params.error;

  const requestHeaders = await headers();
  const accessEmail = requestHeaders.get("cf-access-authenticated-user-email");
  const behindAccess = Boolean(accessEmail);

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
            {behindAccess
              ? `Cloudflare Access で認証されました（${accessEmail}）。サインインしています…`
              : "このアプリは Cloudflare Access 経由でのみアクセスできます。"}
          </p>

          <div className="mt-6">
            <LoginForm
              callbackUrl={callbackUrl}
              error={error}
              behindAccess={behindAccess}
            />
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
