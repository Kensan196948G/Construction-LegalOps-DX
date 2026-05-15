import { redirect } from "next/navigation";

/**
 * ルート `/` は常に `/dashboard` へリダイレクト。
 * 未認証ユーザは middleware (Auth & Config Team) が `/login` に飛ばす。
 */
export default function RootPage(): never {
  redirect("/dashboard");
}
