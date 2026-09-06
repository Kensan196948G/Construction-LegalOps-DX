import type { Metadata } from "next";
import AntitrustCompliancePage from "./page-client";

export const metadata: Metadata = {
  title: "独禁法・入札談合コンプライアンス",
  description:
    "独禁法チェック・入札談合リスクチェック・競合接触記録・接待管理・研修履歴を管理します",
};

export default function Page() {
  return <AntitrustCompliancePage />;
}
