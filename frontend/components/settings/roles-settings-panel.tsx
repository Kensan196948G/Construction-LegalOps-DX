import { CheckCircle2, XCircle } from "lucide-react";

const ROLES = [
  {
    id: "admin", label: "管理者", desc: "全機能へのアクセス権。ユーザ管理・設定変更が可能。",
    perms: { view_contract: true, edit_contract: true, approve: true, admin: true, audit: true },
  },
  {
    id: "legal_lead", label: "法務リード", desc: "法務部門のリーダー。承認権限あり。",
    perms: { view_contract: true, edit_contract: true, approve: true, admin: false, audit: false },
  },
  {
    id: "legal_member", label: "法務担当", desc: "契約レビュー・AI 相談の実行担当。",
    perms: { view_contract: true, edit_contract: true, approve: false, admin: false, audit: false },
  },
  {
    id: "manager", label: "部門長", desc: "契約の閲覧と最終承認が可能。",
    perms: { view_contract: true, edit_contract: false, approve: true, admin: false, audit: false },
  },
  {
    id: "site_member", label: "現場担当", desc: "申請の起票・閲覧のみ。",
    perms: { view_contract: true, edit_contract: false, approve: false, admin: false, audit: false },
  },
  {
    id: "auditor", label: "監査担当", desc: "監査ログの閲覧専用。",
    perms: { view_contract: true, edit_contract: false, approve: false, admin: false, audit: true },
  },
];

const PERM_COLS = [
  { key: "view_contract", label: "閲覧" },
  { key: "edit_contract", label: "編集" },
  { key: "approve", label: "承認" },
  { key: "admin", label: "管理" },
  { key: "audit", label: "監査" },
];

type Perm = { view_contract: boolean; edit_contract: boolean; approve: boolean; admin: boolean; audit: boolean };

export function RolesSettingsPanel() {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium text-muted-foreground w-32">ロール</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">説明</th>
            {PERM_COLS.map(p => (
              <th key={p.key} className="px-3 py-3 text-center font-medium text-muted-foreground w-16">{p.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROLES.map(r => (
            <tr key={r.id} className="border-b last:border-0">
              <td className="px-4 py-3 font-semibold">{r.label}</td>
              <td className="px-4 py-3 text-xs text-muted-foreground">{r.desc}</td>
              {PERM_COLS.map(p => (
                <td key={p.key} className="px-3 py-3 text-center">
                  {(r.perms as Perm)[p.key as keyof Perm]
                    ? <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-500" />
                    : <XCircle className="mx-auto h-4 w-4 text-muted-foreground/30" />
                  }
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default RolesSettingsPanel;
