"use client";

import { FileText, FileImage, File } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ContractDocument } from "@/lib/api/schemas";

interface Props {
  contractId: string;
  documents?: ContractDocument[];
}

const FileIcon = ({ docType }: { docType: string }) => {
  if (docType === "photo" || docType === "image") {
    return <FileImage className="h-5 w-5 text-blue-400" aria-hidden="true" />;
  }
  if (docType === "contract" || docType === "spec" || docType === "site_rule") {
    return <FileText className="h-5 w-5 text-red-400" aria-hidden="true" />;
  }
  return <File className="h-5 w-5 text-muted-foreground" aria-hidden="true" />;
};

function docTypeLabel(docType: string): string {
  switch (docType) {
    case "contract":
      return "契約書";
    case "spec":
      return "仕様書";
    case "site_rule":
      return "施工要領";
    default:
      return docType;
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return value;
  }
}

export function ContractAttachmentsList({ contractId: _, documents = [] }: Props) {
  if (documents.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        契約パッケージ文書はまだ登録されていません。文書のアップロードから登録できます。
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((d) => (
        <div key={d.id} className="flex items-center gap-3 rounded-md border p-3 hover:bg-muted/50">
          <FileIcon docType={d.doc_type} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{d.title}</p>
            <p className="text-xs text-muted-foreground">
              {formatDate(d.doc_date)} • v{d.version}
            </p>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs">
            {docTypeLabel(d.doc_type)}
          </Badge>
        </div>
      ))}
    </div>
  );
}
export default ContractAttachmentsList;
