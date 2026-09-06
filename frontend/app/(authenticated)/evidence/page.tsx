import type { Metadata } from "next";
import EvidencePage from "./page-client";

export const metadata: Metadata = {
  title: "証拠管理",
  description: "証拠保管庫・Chain of Custody・証拠タイムライン・Legal Hold 解除承認を管理します",
};

export default function Page() {
  return <EvidencePage />;
}
