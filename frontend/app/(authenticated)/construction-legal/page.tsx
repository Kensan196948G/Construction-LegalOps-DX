import type { Metadata } from "next";
import ConstructionLegalPage from "./page-client";

export const metadata: Metadata = {
  title: "建設業法務チェック",
  description: "建設業法・許可・届出の法令コンプライアンスチェック",
};

export default function Page() {
  return <ConstructionLegalPage />;
}
