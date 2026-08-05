"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileSearch,
  FolderKanban,
  MessageSquareText,
  Workflow,
  ShieldAlert,
  ClipboardCheck,
  FileText,
  BookOpen,
  ScrollText,
  Settings,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  HardHat,
  CalendarClock,
  Building2,
  Swords,
  FileDiff,
  ReceiptText,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/components/lib/utils";
import { Button } from "@/components/ui/button";

export interface SidebarNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  group?: string;
}

export const sidebarNavItems: SidebarNavItem[] = [
  { label: "ダッシュボード", href: "/dashboard", icon: LayoutDashboard, group: "main" },
  { label: "契約書レビュー", href: "/reviews", icon: FileSearch, group: "contracts" },
  { label: "契約台帳", href: "/contracts", icon: FolderKanban, group: "contracts" },
  { label: "契約申請・稟議", href: "/applications", icon: ClipboardList, group: "contracts" },
  { label: "承認ワークフロー", href: "/workflows", icon: Workflow, group: "contracts" },
  { label: "変更契約・クレーム", href: "/change-orders", icon: FileDiff, group: "contracts" },
  { label: "法務相談", href: "/consultations", icon: MessageSquareText, group: "legal" },
  { label: "支払・検収コンプライアンス", href: "/payments", icon: ReceiptText, group: "legal" },
  { label: "リスク管理", href: "/risks", icon: ShieldAlert, group: "legal" },
  { label: "建設業法務チェック", href: "/construction-legal", icon: HardHat, group: "legal" },
  { label: "契約期限・更新管理", href: "/deadlines", icon: CalendarClock, group: "legal" },
  { label: "取引先・協力会社管理", href: "/partners", icon: Building2, group: "legal" },
  { label: "紛争・クレーム管理", href: "/disputes", icon: Swords, group: "legal" },
  { label: "コンプライアンスチェック", href: "/compliance", icon: ClipboardCheck, group: "quality" },
  { label: "ひな形管理", href: "/templates", icon: FileText, group: "quality" },
  { label: "ナレッジベース", href: "/knowledge", icon: BookOpen, group: "quality" },
  { label: "レポート・分析", href: "/reports", icon: BarChart3, group: "quality" },
  { label: "監査ログ", href: "/audit-logs", icon: ScrollText, group: "admin" },
  { label: "管理設定", href: "/settings", icon: Settings, group: "admin" },
];

export interface SidebarProps extends React.HTMLAttributes<HTMLElement> {
  collapsed?: boolean;
  onToggleCollapsed?: (next: boolean) => void;
}

export function Sidebar({
  className,
  collapsed: collapsedProp,
  onToggleCollapsed,
  ...props
}: SidebarProps) {
  const pathname = usePathname();
  const [internalCollapsed, setInternalCollapsed] = React.useState(false);
  const isControlled = typeof collapsedProp === "boolean";
  const collapsed = isControlled ? collapsedProp : internalCollapsed;

  const toggle = () => {
    const next = !collapsed;
    if (!isControlled) setInternalCollapsed(next);
    onToggleCollapsed?.(next);
  };

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r bg-card transition-[width] duration-200",
        collapsed ? "w-16" : "w-64",
        className
      )}
      aria-label="メインナビゲーション"
      {...props}
    >
      <div className="flex h-16 items-center justify-between border-b px-4">
        {!collapsed ? (
          <span className="text-sm font-semibold tracking-tight">
            Construction LegalOps
          </span>
        ) : (
          <span className="sr-only">Construction LegalOps</span>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={collapsed ? "サイドバーを開く" : "サイドバーを閉じる"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-4">
        <ul className="flex flex-col gap-1">
          {sidebarNavItems.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href || pathname?.startsWith(item.href + "/");
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                    active && "bg-accent text-accent-foreground",
                    collapsed && "justify-center px-2"
                  )}
                  aria-current={active ? "page" : undefined}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

export default Sidebar;
