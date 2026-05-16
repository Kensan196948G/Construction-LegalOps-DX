import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const USERS = [
  { id: "u1", name: "田中 太郎", email: "tanaka@example.com", role: "legal_lead", dept: "法務部", status: "active" },
  { id: "u2", name: "鈴木 花子", email: "suzuki@example.com", role: "legal_member", dept: "法務部", status: "active" },
  { id: "u3", name: "佐藤 一郎", email: "sato@example.com", role: "manager", dept: "工事部", status: "active" },
  { id: "u4", name: "山田 美咲", email: "yamada@example.com", role: "site_member", dept: "工事部", status: "active" },
  { id: "u5", name: "高橋 健二", email: "takahashi@example.com", role: "admin", dept: "管理部", status: "active" },
  { id: "u6", name: "伊藤 直美", email: "ito@example.com", role: "auditor", dept: "管理部", status: "active" },
  { id: "u7", name: "渡辺 誠", email: "watanabe@example.com", role: "legal_member", dept: "法務部", status: "inactive" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "管理者", legal_lead: "法務リード", legal_member: "法務担当",
  manager: "部門長", site_member: "現場担当", auditor: "監査担当",
};

export function UsersSettingsPanel() {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>氏名</TableHead>
            <TableHead>メール</TableHead>
            <TableHead className="w-28">ロール</TableHead>
            <TableHead className="w-24">部署</TableHead>
            <TableHead className="w-20">状態</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {USERS.map(u => (
            <TableRow key={u.id}>
              <TableCell className="text-sm font-medium">{u.name}</TableCell>
              <TableCell className="text-xs text-muted-foreground truncate max-w-[180px]">{u.email}</TableCell>
              <TableCell><Badge variant="outline" className="text-xs">{ROLE_LABELS[u.role] ?? u.role}</Badge></TableCell>
              <TableCell className="text-xs">{u.dept}</TableCell>
              <TableCell>
                <Badge variant={u.status === "active" ? "default" : "secondary"} className="text-xs">
                  {u.status === "active" ? "有効" : "無効"}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
export default UsersSettingsPanel;
