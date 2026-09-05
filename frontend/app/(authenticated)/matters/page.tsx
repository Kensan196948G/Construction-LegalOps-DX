import type { Metadata } from "next";
import MattersPage from "./page-client";

export const metadata: Metadata = {
  title: "法務案件",
  description: "契約を越えた法務案件（Matter）を台帳・タイムライン・契約リンクで管理します",
};

export default function Page() {
  return <MattersPage />;
}
