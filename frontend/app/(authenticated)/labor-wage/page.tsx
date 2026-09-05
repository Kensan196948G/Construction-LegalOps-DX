import type { Metadata } from "next";
import LaborWagePage from "./page-client";

export const metadata: Metadata = {
  title: "労務費基準",
  description: "工種・都道府県別の労務費基準値を管理し、見積単価の乖離率を判定します",
};

export default function Page() {
  return <LaborWagePage />;
}
