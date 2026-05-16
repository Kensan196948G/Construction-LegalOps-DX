import { FileText, FileImage, File } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const MOCK_ATTACHMENTS = [
  { id: "a1", name: "工事請負契約書_v3.pdf", type: "pdf", size: "2.4 MB", uploadedBy: "田中 太郎", uploadedAt: "2026/05/10" },
  { id: "a2", name: "工事内訳明細書.xlsx", type: "xlsx", size: "856 KB", uploadedBy: "鈴木 花子", uploadedAt: "2026/05/11" },
  { id: "a3", name: "現場写真_着工前.jpg", type: "image", size: "3.1 MB", uploadedBy: "山田 美咲", uploadedAt: "2026/05/12" },
  { id: "a4", name: "施工体系図.pdf", type: "pdf", size: "1.2 MB", uploadedBy: "佐藤 一郎", uploadedAt: "2026/05/13" },
  { id: "a5", name: "安全衛生計画書.pdf", type: "pdf", size: "980 KB", uploadedBy: "田中 太郎", uploadedAt: "2026/05/14" },
];

const FileIcon = ({ type }: { type: string }) => {
  if (type === "image") return <FileImage className="h-5 w-5 text-blue-400" />;
  if (type === "pdf") return <FileText className="h-5 w-5 text-red-400" />;
  return <File className="h-5 w-5 text-muted-foreground" />;
};

interface Props { contractId: string; }

export function ContractAttachmentsList({ contractId: _ }: Props) {
  return (
    <div className="space-y-2">
      {MOCK_ATTACHMENTS.map(a => (
        <div key={a.id} className="flex items-center gap-3 rounded-md border p-3 hover:bg-muted/50">
          <FileIcon type={a.type} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{a.name}</p>
            <p className="text-xs text-muted-foreground">{a.size} • {a.uploadedBy} • {a.uploadedAt}</p>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs uppercase">{a.type}</Badge>
        </div>
      ))}
    </div>
  );
}
export default ContractAttachmentsList;
