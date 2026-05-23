import type { Metadata } from "next";
import ApplicationsPage from "./page-client";

export const metadata: Metadata = {
  title: "契約申請・稟議",
  description: "契約申請・稟議の承認フローを管理します",
};

export default function Page() {
  return <ApplicationsPage />;
}
