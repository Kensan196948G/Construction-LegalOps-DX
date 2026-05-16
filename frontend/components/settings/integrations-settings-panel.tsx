import { CheckCircle2, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const INTEGRATIONS = [
  {
    id: "hennge",
    name: "HENNGE One",
    desc: "OIDC シングルサインオン認証",
    status: "connected",
    detail: "テナント ID: hennge-tenant-001",
  },
  {
    id: "entra",
    name: "Microsoft Entra ID",
    desc: "Azure AD によるユーザ同期・MFA",
    status: "connected",
    detail: "テナント ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  },
  {
    id: "m365",
    name: "Microsoft 365",
    desc: "SharePoint Online 連携・Teams 通知",
    status: "connected",
    detail: "SharePoint サイト: const-legal.sharepoint.com",
  },
  {
    id: "directcloud",
    name: "DirectCloud",
    desc: "社内文書・契約書ストレージ",
    status: "connected",
    detail: "接続先: directcloud.example.com",
  },
  {
    id: "claude",
    name: "Claude API（Anthropic）",
    desc: "AI 契約レビュー・法務相談エンジン",
    status: "connected",
    detail: "モデル: claude-opus-4-7（最新）",
  },
  {
    id: "smtp",
    name: "メール通知（SMTP）",
    desc: "ワークフロー・アラート通知",
    status: "pending",
    detail: "設定待ち — SMTP サーバ情報を入力してください",
  },
];

export function IntegrationsSettingsPanel() {
  return (
    <div className="space-y-3">
      {INTEGRATIONS.map(int => (
        <div key={int.id} className="flex items-start gap-3 rounded-md border p-4">
          {int.status === "connected"
            ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
            : <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
          }
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold">{int.name}</p>
              <Badge variant={int.status === "connected" ? "default" : "secondary"} className="text-xs">
                {int.status === "connected" ? "接続済み" : "設定待ち"}
              </Badge>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{int.desc}</p>
            <p className="mt-0.5 text-xs font-mono text-muted-foreground">{int.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
export default IntegrationsSettingsPanel;
