"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  Sun,
  Moon,
  User,
  LogOut,
  Settings,
  ChevronDown,
  CheckCheck,
  Loader2,
  Menu,
} from "lucide-react";
import { useTheme } from "next-themes";
import { signOut } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { notificationsApi } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/use-users";

interface NotificationRow {
  id: number | string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "ライトモードに切り替え" : "ダークモードに切り替え"}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

function NotificationsDropdown() {
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const result = await notificationsApi.list({ page: 1, page_size: 10 });
      setItems(
        result.items.map((n) => ({
          id: n.id,
          title: n.title,
          body: n.body ?? null,
          link: n.link ?? null,
          read_at: n.read_at ?? null,
          created_at: n.created_at,
        })),
      );
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const unread = items.filter((n) => !n.read_at).length;

  const markAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setItems((prev) => prev.map((n) => ({ ...n, read_at: new Date().toISOString() })));
    } catch {
      // 失敗時は何もしない（次回取得で実状態に追随）
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="通知">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute right-1 top-1 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-3 py-2">
          <p className="text-sm font-semibold">通知</p>
          <div className="flex items-center gap-2">
            {unread > 0 && (
              <Badge variant="secondary" className="text-xs">
                {unread} 件未読
              </Badge>
            )}
            {unread > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <CheckCheck className="h-3 w-3" aria-hidden="true" />
                全て既読
              </button>
            )}
          </div>
        </div>
        <DropdownMenuSeparator />
        {loading && (
          <div className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            読み込み中…
          </div>
        )}
        {!loading && error && (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            通知を取得できませんでした
          </p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            通知はありません
          </p>
        )}
        {!loading &&
          !error &&
          items.map((n) => (
            <DropdownMenuItem key={n.id} className="flex flex-col items-start gap-0.5 px-3 py-2.5">
              <span className="text-sm leading-snug">{n.title}</span>
              {n.body && (
                <span className="line-clamp-2 text-xs text-muted-foreground">{n.body}</span>
              )}
              <span className="text-xs text-muted-foreground">
                {new Date(n.created_at).toLocaleString("ja-JP")}
              </span>
            </DropdownMenuItem>
          ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const { data: me } = useCurrentUser();
  const name = me?.display_name ?? me?.email?.split("@")[0] ?? "ユーザー";
  const roleLabel = me?.role ?? "";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="flex items-center gap-2 px-2" aria-label="ユーザーメニュー">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {name.slice(0, 1)}
          </span>
          <span className="hidden text-sm font-medium sm:inline">{name}</span>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <div className="px-3 py-2">
          <p className="text-sm font-medium">{name}</p>
          <p className="text-xs text-muted-foreground">{me?.email ?? ""}</p>
          {roleLabel && (
            <p className="mt-0.5 text-xs text-muted-foreground">ロール: {roleLabel}</p>
          )}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <User className="mr-2 h-4 w-4" />
          プロフィール
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Settings className="mr-2 h-4 w-4" />
          設定
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="mr-2 h-4 w-4" />
          ログアウト
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppHeader({ onMenuClick }: { onMenuClick?: () => void }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-card px-4 lg:px-6">
      <div className="flex items-center gap-2">
        {onMenuClick && (
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={onMenuClick}
            aria-label="メニューを開く"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </Button>
        )}
        <p className="text-sm font-medium text-muted-foreground">
          Construction-LegalOps-DX
        </p>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <NotificationsDropdown />
        <UserMenu />
      </div>
    </header>
  );
}

export default AppHeader;
