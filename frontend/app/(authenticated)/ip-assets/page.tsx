import type { Metadata } from "next";
import IpAssetsPage from "./page-client";

export const metadata: Metadata = {
  title: "知財台帳",
  description: "特許・意匠・商標の出願情報を JPO 特許情報取得 API と連携して管理します",
};

export default function Page() {
  return <IpAssetsPage />;
}
