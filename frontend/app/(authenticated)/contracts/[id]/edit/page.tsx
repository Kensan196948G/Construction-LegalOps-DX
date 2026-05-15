import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ContractEditForm } from "@/components/contracts/contract-edit-form";

export const metadata: Metadata = {
  title: "契約編集",
};

interface ContractEditPageProps {
  params: Promise<{ id: string }>;
}

async function getContractForEdit(id: string) {
  // Stub. Loop 4-5 で実 API に置換。
  if (!id) return null;
  return null;
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
        <p className="text-xs text-muted-foreground">契約 ID: {id}</p>
        <h1 className="mt-1 text-2xl font-bold text-foreground">契約情報を編集</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          メタデータ（タイトル・相手方・金額等）を変更します。本文・条項は別画面から編集します。
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>基本情報</CardTitle>
        </CardHeader>
        <CardContent>
          <ContractEditForm contractId={id} initialValues={contract} />
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        変更内容は監査ログに完全な差分付きで記録されます。
      </p>
    </div>
  );
}
