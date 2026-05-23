import type { Metadata } from "next";
import PartnersPage from "./page-client";

export const metadata: Metadata = {
  title: "取引先・協力会社管理",
  description: "取引先・協力会社の契約・リスク情報を管理します",
};

export default function Page() {
  return <PartnersPage />;
}
