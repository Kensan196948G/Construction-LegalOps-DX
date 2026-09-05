import type { Metadata } from "next";
import SearchPage from "./page-client";

export const metadata: Metadata = {
  title: "契約検索",
  description: "契約メタデータ・条項本文・契約文書を横断検索します",
};

export default function Page() {
  return <SearchPage />;
}
