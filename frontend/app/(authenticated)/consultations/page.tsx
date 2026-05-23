import type { Metadata } from "next";
import ConsultationsPage from "./page-client";

export const metadata: Metadata = {
  title: "法務相談",
  description: "AI による法務相談チャット — 回答は参考情報です",
};

export default function Page() {
  return <ConsultationsPage />;
}
