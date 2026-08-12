import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ContractEditForm } from "@/components/contracts/contract-edit-form";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { contractsApi } from "@/lib/api/endpoints";

export const metadata: Metadata = {
  title: "契約編集",
};

interface ContractEditPageProps {
  params: Promise<{ id: string }>;
}

async function getContractForEdit(id: string) {
  const cleanup = await bindServerSession();
  try {
    return await contractsApi.get(id);
  } catch {
    return null;
  } finally {
    cleanup();
  }
}

export default async function ContractEditPage({ params }: ContractEditPageProps) {
  const { id } = await params;
  const contract = await getContractForEdit(id);

  if (!contract) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-xs text-muted-foreground">
          契約 ID: {contract.id} / 版: {contract.version ?? 1}
        </p>
        <h1 className="mt-1 text-2xl font-bold text-foreground">契約情報を編集</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          メタデータ（タイトル・相手方・金額・期間等）を変更します。本文・条項は別画面から編集します。
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>基本情報</CardTitle>
        </CardHeader>
        <CardContent>
          <ContractEditForm contract={contract} />
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        変更内容は監査ログに完全な差分付きで記録されます。楽観ロック（version）により、
        複数ユーザーによる同時編集の競合を検出します。
      </p>
    </div>
  );
}
