# フロントエンド設計 — Construction-LegalOps-DX

最終更新: 2026-05-16
版数: v1.0 (Draft)
所管: アーキテクチャドキュメントチーム

技術スタック:
- Next.js 15 (App Router) + React 19
- TypeScript 5.x (strict)
- React Server Components (RSC) を主、Client Components は必要箇所のみ
- Tailwind CSS + shadcn/ui (Radix Primitives)
- TanStack Query (Client 限定。fetch は基本 RSC)
- react-hook-form + zod
- next-intl (将来の i18n 拡張)

---

## 1. 設計原則

1. **Server Components ファースト**: RSC でフェッチし HTML を返す。Client Component (`'use client'`) は対話 UI のみに限定。
2. **データ取得は Backend API のみ**: フロントから直接 SharePoint/Entra ID は呼ばない。
3. **AI 出力には免責バナーを常設**: AI レビュー結果を含む画面の最上部に固定表示。
4. **アクセシビリティ AA**: shadcn/ui の Radix Primitives を活用、フォーカスリング・キーボード操作・aria 属性を担保。
5. **デザイントークン**: Tailwind の `theme.extend` に色 / 余白 / タイポを集中。
6. **状態は URL ファースト**: フィルタ・ページャ・タブは URL クエリで保持し、リロード / 共有可能に。
7. **読みやすさ優先**: 業務システムとして 1 行情報量を厳選、最大幅 1440px、本文 14〜16 px。
8. **エラー / ローディング / 空状態**: 全画面の必須 3 状態を最低限実装。
9. **i18n レディ**: 文言は `messages/ja.json` に集約 (MVP は ja のみ)。
10. **テスト**: Playwright (E2E) + Vitest (unit) + Storybook (UI スナップショット)。

---

## 2. ルーティング (App Router)

`app/` 配下のルート構造を以下に定義する。`(auth)` のようなルートグループで認証要否を切り分け、`layout.tsx` で共通シェルを提供する。

```
app/
  layout.tsx                  # ルートレイアウト (HTML, フォント, テーマ)
  page.tsx                    # 「/」: 未認証は /login、認証済みは /dashboard へ
  (auth)/
    login/page.tsx            # /login (SSO 起動)
    callback/page.tsx         # /auth/callback (OIDC 戻り) -- ※ 実体は /api ルート想定
  (app)/                      # 認証必須シェル
    layout.tsx                # ヘッダ + サイドバー + 免責バナー領域
    dashboard/page.tsx        # /dashboard
    contracts/
      page.tsx                # /contracts (一覧)
      new/page.tsx            # /contracts/new (起案)
      [id]/
        page.tsx              # /contracts/[id] (詳細)
        edit/page.tsx         # /contracts/[id]/edit
        reviews/page.tsx      # /contracts/[id]/reviews
        clauses/page.tsx      # /contracts/[id]/clauses
        workflow/page.tsx     # /contracts/[id]/workflow
        history/page.tsx      # /contracts/[id]/history (監査)
    reviews/page.tsx          # /reviews (横断レビュー一覧)
    workflows/
      page.tsx                # /workflows
      [id]/page.tsx           # /workflows/[id]
    risks/page.tsx            # /risks (ヒートマップ + 一覧)
    compliance/page.tsx       # /compliance
    templates/page.tsx        # /templates
    knowledge/
      page.tsx                # /knowledge
      [id]/page.tsx           # /knowledge/[id]
    audit-logs/page.tsx       # /audit-logs
    reports/page.tsx          # /reports
    settings/
      page.tsx                # /settings
      users/page.tsx          # /settings/users
      departments/page.tsx    # /settings/departments
      workflows/page.tsx      # /settings/workflows
```

### 2.1 ナビゲーション (11 メニュー)

| 表示順 | ラベル | パス | 主要ロール |
|--------|--------|------|-----------|
| 1 | ダッシュボード | `/dashboard` | 全員 |
| 2 | 契約管理 | `/contracts` | 全員 (RLS) |
| 3 | レビュー | `/reviews` | drafter+ |
| 4 | ワークフロー | `/workflows` | drafter+ |
| 5 | リスク管理 | `/risks` | viewer+ |
| 6 | コンプライアンス | `/compliance` | reviewer+ |
| 7 | テンプレート | `/templates` | drafter+ |
| 8 | ナレッジ | `/knowledge` | 全員 |
| 9 | 監査ログ | `/audit-logs` | auditor / admin |
| 10 | レポート | `/reports` | approver+ |
| 11 | 設定 | `/settings` | admin |

---

## 3. レイアウト構造

```
+----------------------------------------------------------+
| TopBar (logo / org switch / search / user menu)          |
+--------+-------------------------------------------------+
|        | AIDisclaimerBanner  (常設、画面遷移しても残す)    |
|        +-------------------------------------------------+
|  Side  |                                                 |
|  Bar   |   <PageHeader />                                |
|  (11)  |   <Breadcrumbs />                               |
|        |   <Content>                                     |
|        |     ... 各ページ ...                             |
|        |   </Content>                                    |
|        +-------------------------------------------------+
|        | <FooterMeta />                                  |
+--------+-------------------------------------------------+
```

`(app)/layout.tsx` で TopBar、SideBar、`AIDisclaimerBanner` を配置する。`AIDisclaimerBanner` は Client Component で固定。ユーザーが閉じても**ページ遷移ごとに再表示**する設計とする (法務上の必須要件)。

---

## 4. AI 免責バナー (常設)

```tsx
// components/system/AIDisclaimerBanner.tsx (Client)
'use client';
import { useState } from 'react';

export function AIDisclaimerBanner() {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-40 border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900"
    >
      <span className="font-semibold">AI 出力に関する重要なお知らせ</span>
      ：本システムが提示する AI レビュー結果は<strong>参考情報</strong>であり、
      法的助言ではありません。最終判断は必ず法務担当者・有資格者が行ってください。
      <button
        onClick={() => setOpen(false)}
        aria-label="バナーを閉じる"
        className="ml-3 underline"
      >
        閉じる
      </button>
    </div>
  );
}
```

ルール:
- `/contracts/[id]/reviews`, `/reviews`, `/risks`, `/knowledge` ではバナーを**閉じても遷移ごとに復帰**。
- AI 結果の各カードにも `Badge: AI 参考情報` を併記。

---

## 5. コンポーネント階層 (主要)

```
<RootLayout>
  <ThemeProvider>
    <QueryClientProvider>       # TanStack Query (Client)
      <AppLayout>               # 認証チェック (RSC で fetch /auth/me)
        <TopBar />
        <SideBar />
        <AIDisclaimerBanner />  # Client, 常設
        <main>
          <Breadcrumbs />
          <PageContent />       # 各ルート page.tsx
        </main>
      </AppLayout>
    </QueryClientProvider>
  </ThemeProvider>
</RootLayout>
```

### 5.1 ドメインコンポーネント

```
components/
  system/
    AIDisclaimerBanner.tsx
    EmptyState.tsx
    ErrorBoundary.tsx
    LoadingSkeleton.tsx
  contracts/
    ContractList.tsx          # RSC
    ContractFilters.tsx       # Client (URL state)
    ContractCard.tsx
    ContractStatusBadge.tsx
    ContractForm.tsx          # Client (react-hook-form + zod)
    ContractDetailHeader.tsx
    ClauseList.tsx
    ClauseCard.tsx
  reviews/
    ReviewSummary.tsx
    ReviewFindingCard.tsx     # AI Badge 付き
    ReviewRunButton.tsx       # Client (POST /reviews)
    RiskBadge.tsx
  workflows/
    WorkflowTimeline.tsx
    StepActionBar.tsx         # 承認 / 差戻し / 委任
  risks/
    RiskHeatmap.tsx           # Server (SVG) + tooltip は Client
    RiskTable.tsx
  audit/
    AuditLogTable.tsx
    HashChainVerifyPanel.tsx  # Client
  shared/
    DataTable.tsx             # 仮想スクロール
    Pagination.tsx            # URL クエリ駆動
    SearchInput.tsx
    DateRangePicker.tsx
    FileUploader.tsx          # Client (multipart, 進捗バー)
```

shadcn/ui からは `Button`, `Card`, `Dialog`, `Sheet`, `Tabs`, `Tooltip`, `Badge`, `Toast`, `DropdownMenu`, `Form` を採用する。

---

## 6. 画面別主要 UX

### 6.1 ダッシュボード (`/dashboard`)

- 自分宛承認待ち、AI レビュー完了一覧、期日アラート、月次の起案件数推移、リスクヒートマップ要約。
- カード型レイアウト、各カードは RSC でフェッチ。

### 6.2 契約一覧 (`/contracts`)

- フィルタ: 状態 / 種別 / 部署 / 期間 / 機密度 / フリーワード。すべて URL クエリで保持。
- 一覧は `DataTable` (仮想スクロール)。
- 行クリックで `/contracts/[id]` へ遷移。
- 起案者は `+ 起案` ボタンから `/contracts/new` へ。

### 6.3 契約詳細 (`/contracts/[id]`)

- タブ: 概要 / 条項 / レビュー / ワークフロー / 添付 / 履歴。
- 上部に状態バッジ + 主要メタ + アクション (`AI レビュー実行`, `提出`, `差戻し`).
- 右側に「関連ナレッジ」「類似契約」を AI 提案 (AI Badge 付き)。

### 6.4 AI レビュー結果 (`/contracts/[id]/reviews`)

- 上部: AI 免責バナー (固定) + 全体リスク
- 一覧: 条項毎の `ReviewFindingCard`、リスクレベル別タブ
- 各カード: 指摘・提案・引用条文。アクションは「採用」「却下」「コメント追加」
- すべての AI 出力に `Badge: AI 参考情報`

### 6.5 ワークフロー (`/workflows`, `/contracts/[id]/workflow`)

- タイムライン UI。ステップごとに承認者・期限・状態。
- 自分が assignee の場合は `承認 / 差戻し / 委任` のアクションバーが下部固定。

### 6.6 リスク (`/risks`)

- 5×5 のヒートマップ (確率 × 影響度)、セルクリックで該当リスク一覧へドリルダウン。

### 6.7 コンプライアンス (`/compliance`)

- チェックリスト適用結果、未対応項目を上位に。改正法情報フィードを併記。

### 6.8 監査ログ (`/audit-logs`)

- 仮想スクロールテーブル。`payload` は折りたたみ JSON ビューア。
- `Hash Chain 検証` ボタン → POST `/audit-logs/verify` → 結果トースト + バナー。

### 6.9 設定 (`/settings`)

- ユーザー / 部署 / ワークフロー / 通知テンプレート / 条項ライブラリ管理。
- `admin` のみアクセス。

---

## 7. 状態管理戦略

| 状態の種類 | 保持先 | 例 |
|-----------|--------|----|
| サーバ由来データ | RSC fetch / TanStack Query (Client) | 契約一覧、レビュー結果 |
| URL state | `useSearchParams` + Next.js navigation | フィルタ、ページ、タブ |
| フォーム state | react-hook-form | 起案フォーム、設定フォーム |
| ローカル UI state | `useState` / `useReducer` | モーダル開閉、トースト |
| グローバル (最小) | React Context | テーマ、ユーザー情報、トースト |

クライアント側 store (Redux/Zustand) は**導入しない**ことを MVP の方針とする。

---

## 8. データフェッチ規約

### 8.1 RSC からの fetch

- `app/(app)/contracts/page.tsx` で `fetch(API_BASE + '/contracts?...', { headers, cache: 'no-store' })` を直接呼ぶ。
- Cookie の Bearer 抽出は Next.js `headers()` を用いてサーバサイドで行う。
- 失敗時は `notFound()` または `redirect('/error')`。

### 8.2 Client からの mutation

- 書き込みは TanStack Query の `useMutation` を使用。
- 成功時は `router.refresh()` を呼んで RSC 側を再取得。
- すべての POST に `Idempotency-Key`: `crypto.randomUUID()` を付与。

### 8.3 エラー処理

- API は RFC 7807。`type` をキーにユーザー向け文言マップを保持。
- `403` は明示的に「権限がありません」表示、`401` はログイン画面へ。

---

## 9. デザインシステム

### 9.1 カラートークン (Tailwind)

```
slate-50  ... 背景
slate-900 ... 本文
amber-50/300/900 ... AI 免責バナー
emerald-* ... 成功 / 低リスク
amber-*   ... 中リスク / 警告
red-*     ... 高リスク / Critical
sky-*     ... プライマリ (アクション)
```

### 9.2 タイポ

- 見出し: Inter / Noto Sans JP, 24/20/18px
- 本文: 14〜16 px
- 等幅 (条項本文 / JSON): JetBrains Mono

### 9.3 余白

- Tailwind スケール `2/3/4/6/8/12` を主に使用。
- カード間: `gap-4`、セクション間: `gap-8`。

---

## 10. アクセシビリティ

- すべてのインタラクティブ要素にフォーカスリング (`focus-visible:ring`)。
- 重要操作は確認ダイアログ (`AlertDialog`)。
- アイコンのみのボタンには `aria-label`。
- 色だけに頼らない (リスクは色 + テキスト + 形状アイコン)。
- ダーク / ライト両モードでコントラスト比 4.5:1 以上。

---

## 11. パフォーマンス

- RSC により初期 HTML を最小に。
- Tailwind 経由で CSS は単一バンドル。
- 画像は `next/image`、契約添付サムネは遅延読込。
- 表は仮想スクロール (`@tanstack/react-virtual`)。
- LCP < 2.5s、CLS < 0.1、INP < 200 ms を目標。

---

## 12. セキュリティ (フロント観点)

- セッションは HttpOnly Cookie (フロントから JS で読まない)。
- CSRF: 状態変更 API は `SameSite=Lax` + `Origin` 検証。
- XSS: React 既定のエスケープに加え、`dangerouslyInnerHTML` 禁止 (Markdown は `react-markdown` + サニタイザ)。
- 機密案件画面では右上に「機密」バッジ + 印刷禁止 CSS (`@media print { body { display:none; } }`) を適用。

---

## 13. テスト戦略

| 種別 | ツール | 対象 |
|------|--------|------|
| 単体 | Vitest + Testing Library | 純関数、Hooks、UI 単体 |
| ビジュアル | Storybook + Chromatic (任意) | コンポーネントカタログ |
| E2E | Playwright | 主要 10 シナリオ |
| アクセシビリティ | axe-core in Playwright | 主要画面 |

---

## 14. ディレクトリ標準

```
frontend/
  app/                    # App Router
  components/             # 再利用 UI
  features/               # 機能別ロジック (hooks, schema, api-client)
  lib/                    # 共通ユーティリティ
  messages/               # i18n
  styles/                 # globals.css, tokens
  tests/                  # Playwright
```

---

## 15. 主要 UX 原則 (要約)

1. 業務効率を最優先 — 1 画面で次の行動が決まる
2. AI は補助、判断は人間 — 常設の免責表示
3. 状態の見える化 — バッジ、タイムライン、ヒートマップ
4. 検索を強くする — 全文 + フィルタ + 履歴
5. 例外操作 (差戻し・委任) を 1 クリックで
6. 監査の透明性 — 全操作が遡れる
7. アクセシビリティと印刷配慮を最初から
8. 失敗をやさしく — エラーは原因と次の一手を示す

---

## 16. API 統合 (Frontend ↔ Backend Integration, Loop 4 追記)

### 16.1 全体図

```
+--------------------------------------------------------------+
|                  Next.js 15 (App Router)                     |
|                                                              |
|  Server Component                Client Component             |
|  -----------------               --------------------          |
|   bindServerSession()             <QueryProvider>             |
|        |                              |                       |
|        v                              v                       |
|   setAuthTokenProvider          useInitApiClient()             |
|        |                              |  (useBindClientSession) |
|        +-------------+----------------+                       |
|                      v                                        |
|             frontend/lib/api/client.ts                        |
|             (axios + interceptors)                            |
|                      |                                        |
|                      |  Authorization: Bearer <accessToken>   |
|                      |  Idempotency-Key (POST/PUT/PATCH/DELETE) |
|                      v                                        |
|             Backend /api/v1/* (FastAPI)                       |
+--------------------------------------------------------------+
```

### 16.2 token bridge

| 経路 | エントリ | bind 関数 |
|------|----------|-----------|
| Server Component / RSC | `app/(authenticated)/**/page.tsx` 冒頭で `await bindServerSession()` | `lib/auth/session-bridge#bindServerSession` |
| Client Component (mutations / refetch) | `<QueryProvider>` 内の `useInitApiClient()` | `lib/auth/session-bridge#useBindClientSession` |

- `next-auth` v5 の `auth()` (server) / `useSession()` (client) から `session.user.accessToken` を取得。
- `setAuthTokenProvider(provider)` で `frontend/lib/api/client.ts` の request interceptor に注入。
- 401 受領時は `setOnUnauthorized` 経由で `signOut({ callbackUrl: "/login" })`。

### 16.3 エラー / リトライ

- `ApiError` (RFC 7807 正規化) を `@tanstack/react-query` の `retry` 判定で利用。
- **4xx はリトライしない**: 401/403/404/409/422 は業務エラー。
- 5xx / transport error のみ最大 2 回リトライ。

### 16.4 Idempotency-Key

- `POST` / `PUT` / `PATCH` / `DELETE` には request interceptor が `crypto.randomUUID()` の値を自動付与。
- 呼出側で `withIdempotencyKey()` 経由で指定済みの場合はそれを尊重。

### 16.5 MSW (テスト用)

- `frontend/__mocks__/msw/handlers.ts`: `{ data, meta }` エンベロープ規約に従ったフィクスチャを既定値として持つ。
- 各テストで `server.use(http.get(..., () => HttpResponse.json(...)))` で個別 override。
- `frontend/__mocks__/msw/server.ts`: Node (Jest) 用 setupServer。

---

## 17. 変更履歴

| 日付 | 版 | 変更内容 |
|------|----|---------|
| 2026-05-16 | v1.0 | 初版作成 |
| 2026-05-16 | v1.1 | Loop 4: API 統合 (token bridge / Idempotency / MSW) 追記 |
