import type { Metadata } from "next";
import DisputeDetailPage from "./page-client";

export const metadata: Metadata = {
  title: "紛争・クレーム詳細管理",
  description: "遅延事象・証拠充足度・主張反論・和解案・訴訟ステージを管理します",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <DisputeDetailPage disputeId={id} />;
}
