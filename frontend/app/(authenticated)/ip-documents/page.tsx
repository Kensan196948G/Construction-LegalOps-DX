import type { Metadata } from "next";
import IpDocumentsPage from "./page-client";

export const metadata: Metadata = {
  title: "審査書類",
  description: "拒絶理由通知書・意見書などの審査書類を収集し AI 解析します",
};

export default function Page() {
  return <IpDocumentsPage />;
}
