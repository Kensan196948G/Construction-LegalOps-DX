import type { Metadata } from "next";
import PartnerRiskPage from "./page-client";

export const metadata: Metadata = {
  title: "協力会社リスク",
  description: "協力会社の期限アラート・Risk Score・定期再審査を管理します",
};

export default function Page() {
  return <PartnerRiskPage />;
}
