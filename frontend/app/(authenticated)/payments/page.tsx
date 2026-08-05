import type { Metadata } from "next";
import PaymentsPage from "./page-client";

export const metadata: Metadata = {
  title: "支払・検収コンプライアンス",
  description: "発注日・受領日・検収日・支払日から法定支払期限（60日ルール等）を判定します",
};

export default function Page() {
  return <PaymentsPage />;
}
