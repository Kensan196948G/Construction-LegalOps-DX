// @ts-check

import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const needsWindowsUncLoaderAlias = process.platform === "win32" && __dirname.startsWith("\\\\");

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
  outputFileTracingRoot: __dirname,
  poweredByHeader: false,
  typedRoutes: true,
  experimental: {
    cpus: Number.parseInt(process.env.NEXT_BUILD_CPUS || "1", 10),
    webpackMemoryOptimizations: true,
  },

  eslint: {
    ignoreDuringBuilds: false,
  },

  typescript: {
    ignoreBuildErrors: false,
  },

  webpack: (config) => {
    config.parallelism = Number.parseInt(process.env.NEXT_WEBPACK_PARALLELISM || "1", 10);
    if (config.cache) {
      config.cache = Object.freeze({ type: "memory" });
    }
    if (needsWindowsUncLoaderAlias) {
      config.resolveLoader = config.resolveLoader || {};
      config.resolveLoader.alias = {
        ...(config.resolveLoader.alias || {}),
        "next-flight-client-entry-loader": path.join(
          __dirname,
          "node_modules/next/dist/build/webpack/loaders/next-flight-client-entry-loader.js",
        ),
      };
    }
    return config;
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
