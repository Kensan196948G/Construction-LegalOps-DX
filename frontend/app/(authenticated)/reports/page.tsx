import type { Metadata } from "next";
import ReportsPage from "./page-client";

export const metadata: Metadata = {
  title: "レポート・分析",
  description: "契約・リスク・法務業務の分析レポート",
};

export default function Page() {
  return <ReportsPage />;
}
