"use client";
import Link from "next/link";
import { cn } from "@/components/lib/utils";

const CATEGORIES = ["建設業法", "下請法", "電子帳簿保存法", "コンプライアンス", "社内規程", "AI利用指針"];
const SOURCES = [["internal_doc","社内文書"],["precedent","判例"],["faq","FAQ"],["playbook","プレイブック"]];

interface Props { selectedCategory?: string; selectedSource?: string; }

export function KnowledgeCategoryNav({ selectedCategory, selectedSource }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">カテゴリ</p>
        <ul className="space-y-1">
          {CATEGORIES.map(c => (
            <li key={c}>
              <Link href={`?category=${c}`} className={cn("block rounded px-2 py-1.5 text-sm hover:bg-accent", selectedCategory === c && "bg-accent font-medium")}>{c}</Link>
            </li>
          ))}
          {selectedCategory && <li><Link href="?" className="block rounded px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground">すべて表示</Link></li>}
        </ul>
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">ソース種別</p>
        <ul className="space-y-1">
          {SOURCES.map(([v, l]) => (
            <li key={v}>
              <Link href={`?source=${v}`} className={cn("block rounded px-2 py-1.5 text-sm hover:bg-accent", selectedSource === v && "bg-accent font-medium")}>{l}</Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
export default KnowledgeCategoryNav;
