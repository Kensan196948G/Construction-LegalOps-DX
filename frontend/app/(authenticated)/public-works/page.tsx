import type { Metadata } from "next";
import PublicWorksPage from "./page-client";

export const metadata: Metadata = {
  title: "公共工事",
  description: "発注機関マスタ・通知期限・協議管理・標準約款チェックを管理します",
};

export default function Page() {
  return <PublicWorksPage />;
}
