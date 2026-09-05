import type { Metadata } from "next";
import JvPage from "./page-client";

export const metadata: Metadata = {
  title: "JV 管理",
  description: "共同企業体の台帳・構成員・協定書・紛争・清算を管理します",
};

export default function Page() {
  return <JvPage />;
}
