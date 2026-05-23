import type { Metadata } from "next";
import DisputesPage from "./page-client";

export const metadata: Metadata = {
  title: "紛争・クレーム管理",
  description: "契約関連の紛争・クレームを管理します",
};

export default function Page() {
  return <DisputesPage />;
}
