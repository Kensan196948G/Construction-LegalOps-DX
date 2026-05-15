import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ContractUploadForm } from "@/components/contracts/contract-upload-form";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";

export const metadata: Metadata = {
  title: "新規契約登録",
  description: "契約書 PDF/Word をアップロードし AI 一次レビューを起動します。",
};

export default function NewContractPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">新規契約登録</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          PDF または Word ファイルをアップロードしてください。アップロード後、
          AI 一次レビューが自動的に起動します。
        </p>
      </header>

      <AiDisclaimerInline>
        AI 一次レビューは参考情報の提示にとどまり、最終的な法的判断は
        法務担当者・顧問弁護士が行います。
      </AiDisclaimerInline>

      <Card>
        <CardHeader>
          <CardTitle>契約書ファイル</CardTitle>
        </CardHeader>
        <CardContent>
          <ContractUploadForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>注意事項</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <ul className="list-disc space-y-1 pl-5">
            <li>アップロード可能な形式: PDF / DOCX (最大 50MB)</li>
            <li>
              個人情報・機微情報を含む場合は、ファイル名に固有情報を含めないでください。
            </li>
            <li>
              アップロード後、全ての操作は監査ログに改ざん不能な形で記録されます。
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
