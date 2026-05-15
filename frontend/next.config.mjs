// @ts-check

/**
 * Next.js 15 設定。
 *
 * - App Router 専用 (`app/` ディレクトリのみ採用)
 * - `output: "standalone"` で Docker multi-stage build に対応
 * - `typedRoutes` で `next/link` の型安全リンクを有効化
 * - ESLint / TypeScript エラーはビルドを止める方針 (CI で必ず検出)
 *
 * `images.remotePatterns` の実値は Loop 4 で SharePoint / Blob Storage 等を反映する。
 *
 * @type {import("next").NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  poweredByHeader: false,

  experimental: {
    typedRoutes: true,
  },

  eslint: {
    ignoreDuringBuilds: false,
  },

  typescript: {
    ignoreBuildErrors: false,
  },

  images: {
    // Loop 4: SharePoint / Azure Blob の信頼ドメインを設定。
    // 実ホスト名は環境変数 SHAREPOINT_HOST / AZURE_BLOB_HOST で上書き可。
    // 未設定時はワイルドカードで全テナントを許容 (本番では具体値を強く推奨)。
    remotePatterns: [
      {
        protocol: "https",
        hostname: process.env.SHAREPOINT_HOST || "*.sharepoint.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: process.env.AZURE_BLOB_HOST || "*.blob.core.windows.net",
        pathname: "/**",
      },
      // Microsoft Graph (ファイル直リン)
      {
        protocol: "https",
        hostname: "graph.microsoft.com",
        pathname: "/**",
      },
    ],
  },

  // 法務 DX 用途のため、AI 出力を埋め込む画面では robots を許可しない。
  // Pages Team の `metadata.robots = { index: false, follow: false }` と合わせて二重防御。
};

export default nextConfig;
