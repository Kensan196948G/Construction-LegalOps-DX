import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldAlert } from "lucide-react";

interface Integrity { verified: boolean; verifiedAt: string | null; tamperedCount: number; }
interface Props { integrity: Integrity; }

export function HashIntegrityBadge({ integrity }: Props) {
  if (integrity.verified) {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="default" className="gap-1 bg-emerald-600 hover:bg-emerald-600">
          <ShieldCheck className="h-3.5 w-3.5" />
          ハッシュ整合性 OK
        </Badge>
        {integrity.verifiedAt && (
          <span className="text-xs text-muted-foreground">検証: {integrity.verifiedAt.replace("T", " ").slice(0, 16)}</span>
        )}
      </div>
    );
  }
  return (
    <Badge variant="destructive" className="gap-1">
      <ShieldAlert className="h-3.5 w-3.5" />
      整合性エラー {integrity.tamperedCount} 件
    </Badge>
  );
}
export default HashIntegrityBadge;
