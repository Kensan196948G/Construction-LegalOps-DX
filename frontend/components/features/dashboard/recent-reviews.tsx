import * as React from "react";
import Link from "next/link";
import { ArrowRight, FileSearch } from "lucide-react";

import { cn } from "@/components/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ContractStatusBadge,
  type ContractStatus,
} from "@/components/features/contracts/contract-status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export interface RecentReviewItem {
  id: string;
  title: string;
  counterparty?: string;
  status: ContractStatus;
  riskScore?: number;
  updatedAt: string;
}

export interface RecentReviewsProps extends React.HTMLAttributes<HTMLDivElement> {
  items: RecentReviewItem[];
  isLoading?: boolean;
  /** 「すべて表示」リンク先 */
  viewAllHref?: string;
  /** 個別レビューの URL ビルダー */
  getItemHref?: (item: RecentReviewItem) => string;
  title?: string;
}

export function RecentReviews({
  items,
  isLoading = false,
  viewAllHref = "/reviews",
  getItemHref = (item) => `/reviews/${item.id}`,
  title = "最近のレビュー",
  className,
  ...props
}: RecentReviewsProps) {
  return (
    <Card className={cn(className)} {...props}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileSearch className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          {title}
        </CardTitle>
        <CardDescription>直近で更新された契約書レビュー</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <ul className="flex flex-col gap-2 px-6 pb-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <li key={i}>
                <Skeleton className="h-12 w-full" />
              </li>
            ))}
          </ul>
        ) : items.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">
            最近の更新はありません。
          </p>
        ) : (
          <ul className="divide-y">
            {items.map((item) => (
              <li key={item.id}>
                <Link
                  href={getItemHref(item)}
                  className="flex items-center justify-between gap-3 px-6 py-3 transition-colors hover:bg-accent"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {item.counterparty ?? "—"} ・ {item.updatedAt}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {item.riskScore != null && (
                      <span className="font-mono text-xs text-muted-foreground">
                        R{item.riskScore}
                      </span>
                    )}
                    <ContractStatusBadge status={item.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <CardFooter className="justify-end">
        <Button asChild variant="ghost" size="sm">
          <Link href={viewAllHref}>
            すべて表示
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

export default RecentReviews;
