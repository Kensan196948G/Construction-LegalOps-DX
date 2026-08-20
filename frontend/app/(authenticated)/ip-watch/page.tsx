import type { Metadata } from "next";
import IpWatchPage from "./page-client";

export const metadata: Metadata = {
  title: "競合出願ウォッチ",
  description: "競合企業の出願を JPO 特許情報取得 API と連携して監視します",
};

export default function Page() {
  return <IpWatchPage />;
}
