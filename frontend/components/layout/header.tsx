"use client";

import * as React from "react";
import { Bell, Search, User, LogOut, Settings } from "lucide-react";

import { cn } from "@/components/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export interface HeaderUser {
  name: string;
  email?: string;
  avatarUrl?: string;
}

export interface HeaderProps extends React.HTMLAttributes<HTMLElement> {
  user?: HeaderUser | null;
  notificationCount?: number;
  onSearch?: (query: string) => void;
  onLogout?: () => void;
}

export function Header({
  className,
  user,
  notificationCount = 0,
  onSearch,
  onLogout,
  ...props
}: HeaderProps) {
  const [query, setQuery] = React.useState("");

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSearch?.(query);
  };

  const initials = (user?.name ?? "?")
    .split(/\s+/)
    .map((s) => s.charAt(0))
    .slice(0, 2)
    .join("");

  return (
    <header
      className={cn(
        "flex h-16 items-center gap-4 border-b bg-background px-4 md:px-6",
        className
      )}
      {...props}
    >
      <form
        onSubmit={handleSubmit}
        className="relative flex-1 max-w-xl"
        role="search"
      >
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="契約書・キーワードを検索"
          aria-label="検索"
          className="pl-9"
        />
      </form>

      <Button
        variant="ghost"
        size="icon"
        aria-label={`通知 ${notificationCount}件`}
        className="relative"
      >
        <Bell className="h-5 w-5" />
        {notificationCount > 0 && (
          <Badge
            variant="destructive"
            className="absolute -right-1 -top-1 h-5 min-w-5 justify-center px-1 text-[10px]"
          >
            {notificationCount > 99 ? "99+" : notificationCount}
          </Badge>
        )}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="flex items-center gap-2 px-2"
            aria-label="ユーザーメニュー"
          >
            <Avatar size="sm">
              {user?.avatarUrl ? (
                <AvatarImage src={user.avatarUrl} alt={user.name} />
              ) : (
                <AvatarFallback>{initials || "U"}</AvatarFallback>
              )}
            </Avatar>
            <span className="hidden text-sm font-medium md:inline">
              {user?.name ?? "未ログイン"}
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="flex flex-col">
              <span className="text-sm">{user?.name ?? "ゲスト"}</span>
              {user?.email && (
                <span className="text-xs text-muted-foreground">
                  {user.email}
                </span>
              )}
            </div>
          </DropdownMenuLabel>
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
          <DropdownMenuItem onClick={onLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            ログアウト
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

export default Header;
