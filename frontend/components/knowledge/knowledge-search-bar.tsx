"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

export function KnowledgeSearchBar({ defaultQuery }: { defaultQuery: string }) {
  const [q, setQ] = useState(defaultQuery);
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const p = new URLSearchParams(sp.toString());
    if (q) p.set("q", q); else p.delete("q");
    router.push(`${pathname}?${p.toString()}`);
  };

  return (
    <form onSubmit={submit} className="flex gap-2">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input value={q} onChange={e => setQ(e.target.value)} placeholder="判例・社内文書・FAQ をキーワード検索..." className="pl-9" />
      </div>
      <Button type="submit">検索</Button>
    </form>
  );
}
export default KnowledgeSearchBar;
