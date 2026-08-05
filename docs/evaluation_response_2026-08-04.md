# 外部評価への対応記録（2026-08-04）

本稿は外部評価（67/100・条件付き導入推奨）を受けた確認結果と対応状況を記録する。

## 対応サマリ

| P0 指摘 | 確認結果 | 対応 | 状態 |
|---|---|---|---|
| P0-1 取適法（旧下請法）未対応 | 資本金のみ・2026 年施行未反映を確認 | 適用マトリクス（資本金＋従業員数）、発注日による新旧切替、60 日支払期日の実日付計算、手形払い禁止・電子記録債権/ファクタリング判定、一方的代金決定禁止、特定運送委託、書面交付事項、取引記録保存を実装 | ✅ 完了 |
| P0-2 改正建設業法・労務費基準 | ルール未実装を確認 | 労務費等内訳（労務費/材料費/安全衛生経費/法定福利費/建退共）、著しく低い見積り・短工期検知、契約前通知、スライド条項を実装 | ✅ 完了 |
| P0-3 建設業法 19 条チェック | 9 キーワードの存在確認のみを確認 | 法定記載事項 11 項目へ拡大、約款・特記仕様書等の文書横断、金額乖離（20% 超）・日付順序検証を実装 | ✅ 完了 |
| P0-4 AI 根拠の強制 | citations が任意・未検証を確認 | 指摘ごとに原文抜粋・法令名/条番号・バージョン/施行日・一次情報 URL（公的機関ホスト限定）・社内規程 ID/版数・ルール ID・信頼度・verdict を必須化。根拠不足は `needs_human_review` へ降格、根拠なき回答は `unverifiable` | ✅ 完了 |
| P0-5 プロンプトインジェクション | 契約本文を生プロンプト投入・防御なしを確認 | 非信頼データマーカー分離、文書内命令無視のシステム指示、JSON Schema 検証、URL 許可リスト、攻撃文書の回帰テストを実装 | ✅ 完了 |
| P0-6 ポリシーと実装の差 | RLS / WORM / Sentinel / Purview 実装なしを確認 | DB RLS（13 テーブル）・案件単位 ACL・倫理壁・Legal Hold・AI 保存期間・WORM 外部出力・Sentinel 転送を実装（後述の最終対応記録参照） | ✅ 完了 |

## 実装内容

### compliance_checker.py（P0-1〜P0-3）

- 新ルール: `toritekihou_*`（適用判定・支払期日・手形等禁止・書面交付・特定運送委託・
  取引記録・発注日未設定）、`construction_law_labor_*`（労務費内訳・低見積・短工期・
  事前通知・スライド）、`construction_law_19_amount_*`・`construction_law_19_date_*`。
- `ContractSnapshot` に従業員数・発注日/受領日/検収日/支払日・取引類型・文書パッケージを追加。
- 適用マトリクスは公取委公式ページ
  （https://www.jftc.go.jp/partnership_package/toritekihou.html）に基づく
  「資本金超 または 従業員数超」の OR 判定。

### ai_review.py / ai_review_service.py / schemas（P0-4〜P0-5）

- `ReviewIssue` に根拠項目 11 種と `verdict` を追加。`AIReviewResult` に
  `requires_human_review` / `citation_gaps` / `guardrail_version` を追加。
- システムプロンプト v2（`contract_review.v2`）で非信頼データ分離・根拠必須・捏造禁止を明示。
- 出力検証: リスクコード形式、verdict 許可値、URL 許可ホスト、信頼度 0〜1 クランプ。
- スタブ出力は検証済み根拠を持たないため `verdict=needs_human_review` を表明。

### テスト・ドキュメント

- ユニット +33 件、合計 996 件 PASS（pytest）、ruff / mypy / bandit クリーン。
- `docs/construction_law_checklist.md`（取適法・労務費基準・19 条拡充）、
  `docs/ai_disclaimer_policy.md`（根拠保証・インジェクション対策）、
  `docs/requirements.md`、`README.md`、`CHANGELOG.md` を更新。

## 残課題（次のサイクルで対応推奨）

### P0-6 未実装部分

- PostgreSQL RLS（`CREATE POLICY` / `ENABLE ROW LEVEL SECURITY`）:
  アプリ接続ユーザーの分離と `current_setting('app.actor_id')` 方式の設計が必要。
- 案件単位 ACL・機密区分・倫理壁（人事/談合/内部通報案件）の DB 実装。
- 監査ログの WORM 相当ストレージへの外部保管（現状はハッシュチェーンのみ）。
- Microsoft Sentinel への転送、Purview DLP の実通信ブロック。
- AI 入出力の保存期間・削除処理、Legal Hold 時の自動削除停止。

### 業務機能（評価の高優先）

- 変更契約・追加工事・クレーム管理（通知期限・失権リスク・累積影響分析）
- 支払・出来高・検収コンプライアンス（会計システム照合）
- 協力会社コンプライアンス台帳（許可・社会保険・CCUS・技術者資格）
- 紛争・事故・債権管理（証拠保全・Legal Hold・経営層集計）

### AI 機能（第 1 優先）

- 一次情報限定 RAG（e-Gov・国交省・公取委・社内規程・承認済み顧問見解）
- 法令改正影響分析、適用法令自動判定、証拠マッピング

## 推奨導入判断

- 限定 PoC / 法務部門並行運用: 推奨
- 低リスク契約の一次レビュー: 条件付き推奨（要人手確認ゲート付き）
- 全社本番正本化: P0-6 および上記残課題の完了後

---

# 最終対応記録（2026-08-05）

上記「残課題」として記載していた項目をすべて実装し、評価（67/100）への最終対応を完了した。

## P0-6（完了）

| 項目 | 実装 |
|---|---|
| PostgreSQL の CREATE POLICY / ENABLE ROW LEVEL SECURITY | `contracts` を起点に 13 テーブルへ適用（migration 006/007）。`app.actor_id` / `app.role` / `app.actor_email` のセッション変数で行可視性を強制 |
| 案件単位 ACL と機密区分 | `access_control_entries`（user / department / role / external_counsel）+ `/contracts/{id}/access-control` API。`contracts.case_category`・`ethical_wall` を正本化 |
| 外部顧問弁護士用の案件限定アクセス | principal_type=external_counsel（メール単位）+ 有効期限付き付与。RLS ポリシーでも照合 |
| 人事・談合調査・内部通報案件の倫理壁 | `ethical_wall=true` 案件は明示許可ユーザー or admin/auditor のみ可視（RLS + アプリ層二重判定） |
| Purview DLP または同等機能の実通信ブロック | `sensitive_detector` / マスキングミドルウェア + `/ai/evidence/verify` の公的ホスト URL 許可リストで外部送信を制限。Purview 接続は config ゲート付き（未設定時は送信なし） |
| WORM 相当ストレージへの監査ログ外部保管 | `audit_export_jobs`（JSONL + Ed25519 署名）と `audit_anchors`（HMAC-SHA256 日次アンカー）の 2 系統。外部シンク未設定時は DB 内アンカーのみ |
| Microsoft Sentinel への転送 | `external_forward_events` アウトボックス + `/security/audit-exports`・`/admin/sentinel/status`。設定不足時は status=blocked（fail-closed） |
| AI 入力・出力の保存期間と削除処理 | `/security/retention-settings`・`/retention` で管理。保存期間超過の AI 出力は result を空化し `retention.delete` を監査記録 |
| Legal Hold 時の自動削除停止 | `legal_hold_cases` / `legal_holds` の active 中はパージをスキップし `retention.blocked` を記録 |
| ハッシュチェーン改ざん防止の強化 | DB 内ハッシュチェーンに加え、日次アンカーの HMAC 署名と外部 WORM 出力を追加（DB 管理者のみでの改ざんを検知可能に） |

## 高優先業務機能（完了）

1. **変更契約・追加工事・クレーム管理** — `/change-orders`（通知期限 14 日自動計算・失権リスク・累積影響・証拠紐付け）
2. **契約文書の優先順位管理** — `/contracts/{id}/documents` + `/consistency`（金額乖離 20% 超・工期逆転・責任帰属矛盾）
3. **支払・出来高・検収コンプライアンス** — `/contracts/{id}/payment-compliance`・`/payments`（60 日/50 日実日計算・遅延利息・手形等禁止・不当減額・保留金）
4. **協力会社コンプライアンス台帳** — `/partners`（許可・社会保険・CCUS・資格・反社・倒産リスクの理由付き自動評価）
5. **紛争・事故・債権管理** — `/disputes`（タイムライン・証拠保全・時効/期限・エクスポージャー集計）

## AI 機能（第 1 優先完了）

1. **一次情報限定 RAG** — `/ai/evidence`（ナレッジベース限定 + 公的機関 URL 許可リスト検証）
2. **法令改正影響分析** — `/compliance/law-change-impact`（取適法施行日を軸に影響契約を抽出）
3. **適用法令自動判定** — `/compliance/applicable-laws`（資本金・従業員数・発注日・公共/民間で根拠付き判定）
4. **契約条項と法定要件の証拠マッピング** — compliance_checker の `rule_id` + citation + evidence を全指摘で保持

## 検証結果（2026-08-05 実測）

| 検証 | 結果 |
|---|---|
| pytest（SQLite 全件） | 876 passed（unit）+ 179 passed / 2 skipped（integration）= **1,055 passed** |
| pytest（PostgreSQL 16 実 DB・migration 001→007 適用済み） | **1,057 passed / 0 failed** |
| ruff / mypy | 全チェック合格 / 0 issues |
| alembic upgrade→downgrade→upgrade（PG 実 DB） | 成功 |
| frontend typecheck / lint / Jest | 全クリーン / 40 passed |

## 残課題（外部連携は設定と運用者の承認待ち）

- Purview DLP / Sentinel の実送信は、Azure リソースと接続情報の提供後に有効化（現状 fail-closed）
- WORM 外部シンク（S3 / Azure Blob / SFTP）は接続先提供後に有効化
- 電子署名・印紙税判定・JV 損益分担・海外契約等は Phase 2 ロードマップ（README スコープ外に明記）
