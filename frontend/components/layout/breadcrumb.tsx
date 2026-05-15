import * as React from "react";
import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

import { cn } from "@/components/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps extends React.HTMLAttributes<HTMLElement> {
  items: BreadcrumbItem[];
  /** 先頭にホームアイコンリンクを表示するか */
  showHome?: boolean;
  homeHref?: string;
}

export function Breadcrumb({
  className,
  items,
  showHome = true,
  homeHref = "/dashboard",
  ...props
}: BreadcrumbProps) {
  return (
    <nav aria-label="パンくずリスト" className={cn("text-sm", className)} {...props}>
      <ol className="flex flex-wrap items-center gap-1 text-muted-foreground">
        {showHome && (
          <li className="flex items-center gap-1">
            <Link
              href={homeHref}
              className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
            >
              <Home className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">ホーム</span>
            </Link>
            {items.length > 0 && (
              <ChevronRight
                className="h-3.5 w-3.5 text-muted-foreground/60"
                aria-hidden="true"
              />
            )}
          </li>
        )}
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;
          return (
            <li key={`${item.label}-${idx}`} className="flex items-center gap-1">
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  className="transition-colors hover:text-foreground"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={cn(isLast && "font-medium text-foreground")}
                  aria-current={isLast ? "page" : undefined}
                >
                  {item.label}
                </span>
              )}
              {!isLast && (
                <ChevronRight
                  className="h-3.5 w-3.5 text-muted-foreground/60"
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumb;
