import type { Metadata } from "next";
import DeadlinesPage from "./page-client";

export const metadata: Metadata = {
  title: "契約期限・更新管理",
  description: "契約の期限・更新期日を一覧管理します",
};

export default function Page() {
  return <DeadlinesPage />;
}
