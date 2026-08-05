import type { Metadata } from "next";
import ChangeOrdersPage from "./page-client";

export const metadata: Metadata = {
  title: "変更契約・クレーム管理",
  description: "設計変更・追加工事・工期延長・価格スライド・クレームを管理します",
};

export default function Page() {
  return <ChangeOrdersPage />;
}
