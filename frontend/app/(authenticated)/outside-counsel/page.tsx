import type { Metadata } from "next";
import OutsideCounselPage from "./page-client";

export const metadata: Metadata = {
  title: "顧問弁護士",
  description: "法律事務所・担当弁護士の台帳と、依頼・回答・確認の管理を行います",
};

export default function Page() {
  return <OutsideCounselPage />;
}
