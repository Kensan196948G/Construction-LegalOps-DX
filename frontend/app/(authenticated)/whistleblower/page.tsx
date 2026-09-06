import type { Metadata } from "next";
import WhistleblowerPage from "./page-client";

export const metadata: Metadata = {
  title: "内部通報・調査",
  description:
    "内部通報の受付・調査担当者限定アクセス・証拠保全・ヒアリング・是正措置を管理します（通報者情報は調査担当者のみ閲覧可）",
};

export default function Page() {
  return <WhistleblowerPage />;
}
