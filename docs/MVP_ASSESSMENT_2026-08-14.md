# 📋 Construction-LegalOps-DX — MVP/Prototype 総合評価（2026-08-14）

> 📌 根拠は実コード・実画面・API 応答・DB 実データ・テスト結果・CI 状態。
> README の主張ではなく実体を検証した結果を記録する。

## 🎯 1. 総合評価

建設業法務特化の契約ライフサイクル管理（契約台帳・AI レビュー・承認ワークフロー・
コンプライアンス・リスク・協力会社・紛争・支払コンプライアンス・ナレッジ）が
FastAPI + Next.js + PostgreSQL(RLS) + Cloudflare 基盤で実装され、主要ユースケースは
**公開 MVP で実際に操作・評価できる状態**にある。

- 🟢 公開 MVP: `https://legalops-mvp.mirai-dx-platform.com`（稼働中・架空データのみ）
- 🟢 backend pytest 1113 passed / ruff 0.16.1 / mypy 2.3.0 clean
- 🟢 frontend typecheck / lint / Jest 43 passed / Docker ビルド成功
- 🟡 P0 は「本番化の人間ゲート」（#23 Vault 投入 / #24 CSP enforce / #50 CF+Neon 本番構築）のみで、
  いずれも本番運用対象外の今回スコープ外。MVP スコープ内の P0 はゼロ。

## 🧭 2. 実装状況マトリクス（2026-08-14 実測）

| 📦 観点 | 📊 状態 | 🔍 根拠 |
|---|---|---|
| 認証（JWT RS256 / Cloudflare Access / dev bypass） | ✅ 実装済み | `backend/app/deps.py`・`test_dev_bypass.py`・公開 URL で実応答 |
| 認可（RBAC / RLS / 案件単位 ACL） | ✅ 実装済み | `tests/integration/test_rbac*.py`・migration 006・PG で RLS |
| 契約 CRUD・編集（楽観ロック） | ✅ 実装済み | 公開 API `GET/POST/PATCH /contracts` 200 |
| 契約詳細・バージョン・条項・監査証跡 | ✅ 実装済み | `contracts/{id}/versions`・`/clauses`・`/audit-trail` |
| AI レビュー（ヒューリスティック stub） | 🟡 部分実装 | 本物の Claude 連携は本番シークレット待ち（fail-closed stub） |
| 法務相談・根拠検索（一次情報 RAG） | ✅ 実装済み | Loop 110・`/ai/evidence` |
| 承認ワークフロー（定義/ステップ/行動） | ✅ 実装済み | `workflows` 1 定義・30 ステップ seed、`workflow_actions` テスト |
| コンプライアンスチェック（機械判定） | ✅ 実装済み | `compliance/checklists`・`checks/{id}/run`・#60 表示修正済 |
| リスク台帳・スコアリング | ✅ 実装済み | `risks` 41 件 seed、`risk_scoring` テスト |
| 協力会社台帳（許可・社会保険・CCUS） | ✅ 実装済み | `partners` 12 件 seed（架空許可番号） |
| 紛争・クレーム管理 | ✅ 実装済み | `disputes` 6 件 seed |
| 支払コンプライアンス（60日/50日・手形検知） | ✅ 実装済み | `payment-compliance` 200・32 レコード（late/手形含む） |
| 変更契約・失権リスク警告 | ✅ 実装済み | `change-orders` 6 件 seed |
| 期限管理（契約実データ） | ✅ 実装済み | Loop 110 でモック廃止 |
| ダッシュボード / KPI / トレンド | ✅ 実装済み | `/dashboard/summary` 200・frontend 実 API |
| 通知（in-app） | ✅ 実装済み | `notifications` 5 件 seed |
| 監査ログ（ハッシュチェーン・エクスポート） | ✅ 実装済み | `audit-logs` 200・demo フラグ分離・`audit_hash_chain` テスト |
| 帳票（CSV/Excel/PDF） | 🟡 部分実装 | 監査 CSV エクスポートあり。履行報告・3条書面等は将来 backlog |
| レート制限 / CORS / CSP / セキュリティヘッダー | ✅ 実装済み | `middleware/rate_limit.py`・nginx security-headers・CSP Report-Only（enforce は #24） |
| ヘルスチェック / readiness | ✅ 実装済み | `/healthz`・`/readyz`（nginx 公開は follow-up で追加）・公開 URL で 200 |
| モック残存 | ✅ 解消済み | Loop 111 で残モック 3 画面を実 API 化。`mock-data.ts` はフォールバック/候補表示のみ |
| テスト / CI（7 ジョブ） | ✅ 実装済み | `.github/workflows/ci.yml`（pytest/ruff/mypy/Jest/build/security） |

## 📌 3. バックログ（P0〜P3）

| 優先度 | 項目 | 状態 | 効果 / 工数 / リスク |
|---|---|---|---|
| P0 | #23 本番 Vault secrets 投入 | 🔒 人間ゲート（対象外） | 本番稼働に必須 / 0.5日 / 秘匿性 |
| P0 | #24 CSP Report-Only → enforce | 🔒 人間ゲート（対象外） | XSS 防御強化 / 0.5日 / 画面崩れ |
| P0 | #50 Cloudflare + Neon 本番構築 | 🔒 人間ゲート（対象外） | 本番基盤 / 数日 / 課金・法務判断 |
| P1 | 外部連携実運用（SharePoint/Teams/desknet's/Claude API） | 📋 バックログ | 実運用 / 高 / 外部承認 |
| P1 | 帳票出力（履行報告・施工体系図・3条書面） | 📋 バックログ | 書類工数削減 / 中 / — |
| P1 | e-BISC/GECS 連携・施工体制台帳の公共要件拡充 | 📋 バックログ | 公共 80% 要件 / 高 / 仕様変動 |
| P1 | 通知のリアルタイム化・エスカレーション | 📋 バックログ | 停滞防止 / 中 / — |
| P2 | アクセシビリティ検証（WCAG 準拠の自動/E2E） | 📋 バックログ | 全社展開 / 中 / — |
| P2 | 表記ゆれ・マスタ整合チェック、データ品質スコア | 📋 バックログ | 入力品質 / 中 / — |
| P2 | MVP 公開 URL への Cloudflare Access（レビュー対象限定） | 📋 バックログ | 公開範囲統制 / 小 / Access 設定 |
| P3 | `/api/v1/health` version 表記の動的化 | 📋 バックログ | 表示整合 / 小 / — |
| P3 | `next lint` 非推奨への ESLint CLI 移行（Next 16 対応） | 📋 バックログ | 将来互換 / 小 / — |

> ✅ 2026-08-14 に #60（compliance neutral 表示）・#64（tunnel UUID 解決）を検証の上クローズ済み。

## 🎭 4. 主要ダミーデータ構成（すべて架空・再生成可能）

| 📋 種別 | 🔢 件数 | 特徴 |
|---|---|---|
| 契約 / レビュー / リスク | 22 / 15 / 41 | `CTR-2026-*`・6 種の契約種別・リスクスコア分布 |
| 承認ワークフロー | 1 定義 / 30 ステップ | 承認・却下・差戻しの状態遷移 |
| 協力会社 | 12 | 許可期限境界（18日後）・反社 `pending`・倒産 `high` 等の異常系 |
| 紛争 / 変更契約 | 6 / 6 | 解決済み〜エスカレーション・回答期限経過（失権警告） |
| 支払 | 32 | 期日超過 `late`・下請への手形払い（取適法違反候補） |
| テンプレート / ナレッジ / 通知 | 10 / 5 / 5 | 標準ひな形・法令解説・承認リマインド |
| 監査ログ | 実データと分離 | `payload.after.demo=true` フラグ付き |

人物名・企業名・案件名・許可番号・金額・日付は実在情報を避けた架空値
（例: みらい建設工業(株)・みらい北幹線道路補修工事・デモ大臣許可（般-2026）第000001号）。
投入は冪等で `scripts/seed_demo_data.py --delete` により削除・再生成可能。検証後も保持している。

## 🧪 5. 検証証跡（2026-08-14 実測）

```text
backend : ruff 0.16.1 All checks passed / mypy 2.3.0 138 files clean
          pytest 1113 passed, 2 skipped（SQLite。PG 専用 RLS のみスキップ）
frontend: typecheck / lint clean、Jest 43 passed（7 suites）
          Docker build OK（node:20.18.0-alpine = CI 同一）
公開 URL: /healthz 200・/ 200
          /readyz 200（follow-up で mvp.conf にプロキシ追加）
          API: contracts(22) partners(12) disputes(6) change-orders(6)
          reviews(15) risks(41) templates(10) knowledge(5) notifications(5)
          GET /contracts/{id} 200・payment-compliance 200
DB      : alembic head=008・payment_records=32・audit demo フラグ確認
secret  : scripts/scan_secrets.sh → No high-confidence secret patterns detected
```

## 🚦 6. MVP / Prototype 判定

- 🟢 **MVP / Prototype: GO**（主要ユースケース実動作・有効なダミーデータ投入/保持・
  主要 UI/API/DB 整合・テスト/ビルド成功・README/設計/起動手順/デモ手順が実装と一致）
- 🟡 **本番化: CONDITIONAL GO**（#23/#24/#50 の人間ゲート完了が前提。本番デプロイは人間判断）

## 📖 7. 参照

- 構築・URL・デモ手順: `docs/MVP_DEPLOYMENT.md`
- 本番承認パケット / 証拠表: `docs/PRODUCTION_APPROVAL_PACKET.md` / `docs/RELEASE_EVIDENCE_MATRIX.md`
