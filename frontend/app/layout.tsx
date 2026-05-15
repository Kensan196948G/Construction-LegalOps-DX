import type { Metadata, Viewport } from "next";
import { Noto_Sans_JP } from "next/font/google";
import "./globals.css";

import { Providers } from "@/components/providers";

const notoSansJp = Noto_Sans_JP({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
  variable: "--font-noto-sans-jp",
});

export const metadata: Metadata = {
  title: {
    default: "Construction-LegalOps-DX",
    template: "%s | Construction-LegalOps-DX",
  },
  description:
    "建設業向け法務 DX プラットフォーム — 契約レビュー・承認ワークフロー・リスク管理を一元化",
  applicationName: "Construction-LegalOps-DX",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f172a",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" suppressHydrationWarning>
      <body className={`${notoSansJp.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
