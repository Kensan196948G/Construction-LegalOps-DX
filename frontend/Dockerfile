# syntax=docker/dockerfile:1.7
# ============================================================================
# Construction-LegalOps-DX  ―  frontend (Next.js 15, App Router, standalone)
#
# Multi-stage build:
#   1) deps    : production + dev 依存を解決
#   2) build   : Next.js `standalone` ビルドを生成
#   3) runner  : non-root (uid=1001) で `node server.js` を起動
#
# 注意:
#   - `next.config.mjs` で `output: "standalone"` が必須
#   - `/api/health` は Pages Team の Route Handler が提供する想定
#   - secret (AUTH_SECRET, ENTRA_ID クレデンシャル等) は **絶対に COPY しない**。
#     ランタイムで Azure Key Vault / Secret Store 経由で注入する。
# ============================================================================

ARG NODE_VERSION=20.18.0

# ----------------------------------------------------------------------------
# Stage 1: deps  ―  依存関係を独立レイヤとしてキャッシュ
# ----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app

# Alpine で next-swc 等 native module 用に必要
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
# package-lock.json が存在しない初期 Loop でも build を通せるよう fallback
RUN if [ -f package-lock.json ]; then \
      npm ci --no-audit --no-fund; \
    else \
      npm install --no-audit --no-fund; \
    fi

# ----------------------------------------------------------------------------
# Stage 2: build  ―  Next.js standalone build
# ----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ----------------------------------------------------------------------------
# Stage 3: runner  ―  最小サーフェスで起動
# ----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# non-root ユーザを作成 (uid/gid = 1001)
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# standalone 出力は `.next/standalone` 配下に server.js と最小 node_modules を含む
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

# `/api/health` を Pages Team が提供する前提。提供されるまで起動だけ通る。
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget --quiet --spider http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "server.js"]
