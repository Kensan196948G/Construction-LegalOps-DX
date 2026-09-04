# Construction-LegalOps-DX 拡張ロードマップ —「法務部門の業務OS」へ

> 状態: **計画（2026-09-04 策定）** — PR マージ後に「承認済み」へ更新し、この文書を Phase 1〜5 の実装計画の正本とする。
> 検証対象コミット: `main` @ `c110afe`（PR #95 / 2026-09-04 時点）
> 更新ルール: フェーズ完了・スコープ変更時は本ファイルを更新し、CHANGELOG / README と整合させる。

---

## 1. 目的

`Construction-LegalOps-DX` は、単純な「契約書 AI レビュー」ではない。
契約レビュー・契約台帳・稟議・承認・変更契約・法務相談・支払・検収・リスク・建設業法・期限・
協力会社・紛争・知財・コンプライアンス・ひな形・ナレッジ・レポート・監査まで、
左メニューだけで **22 領域** を既に持つ（実測、§2）。

本ロードマップは、既存機能との重複をできるだけ除去した上で、
「**建設業 CLM + Legal Matter Management + Construction Compliance +
Regulatory Intelligence + AI Legal Agent**」という **法務部門の業務 OS** に近づけるための
追加機能計画（272 候補を整理・優先度付け・5 フェーズ化）を定める。

---

## 2. 現状インベントリ（2026-09-04 実測・main @ c110afe）

### 2.1 画面（左メニュー 22 領域・`frontend/components/layout/sidebar.tsx`）

| # | メニュー | ルート |
| - | --- | --- |
| 1 | ダッシュボード | `/dashboard` |
| 2 | 契約書レビュー | `/reviews` |
| 3 | 契約台帳 | `/contracts` |
| 4 | 契約申請・稟議 | `/applications` |
| 5 | 承認ワークフロー | `/workflows` |
| 6 | 変更契約・クレーム | `/change-orders` |
| 7 | 法務相談 | `/consultations` |
| 8 | 支払・検収コンプライアンス | `/payments` |
| 9 | リスク管理 | `/risks` |
| 10 | 建設業法務チェック | `/construction-legal` |
| 11 | 契約期限・更新管理 | `/deadlines` |
| 12 | 取引先・協力会社管理 | `/partners` |
| 13 | 紛争・クレーム管理 | `/disputes` |
| 14 | 知財台帳 | `/ip-assets` |
| 15 | 競合出願ウォッチ | `/ip-watch` |
| 16 | 審査書類・AI 解析 | `/ip-documents` |
| 17 | コンプライアンスチェック | `/compliance` |
| 18 | ひな形管理 | `/templates` |
| 19 | ナレッジベース | `/knowledge` |
| 20 | レポート・分析 | `/reports` |
| 21 | 監査ログ | `/audit-logs` |
| 22 | 管理設定 | `/settings` |

### 2.2 Backend（FastAPI / SQLAlchemy / Alembic / PostgreSQL 16）

- API v1 ルーター（`backend/app/api/v1/`、20 本）:
  `admin / audit_logs / auth / business / compliance / contracts / dashboard /
  governance / health / ip / knowledge / legal_ai / notifications / reviews /
  risks / security / templates / uploads / users / workflows`
- サービス（`backend/app/services/` 約 50 本）: `contract_service / clause_extractor /
  change_order_service / dispute_service / payment_compliance / partner_service /
  legal_hold_service / retention_service / compliance_checker / applicable_law /
  law_change_impact / legal_rag / evidence_lookup / similarity_search /
  sharepoint_service / workflow_engine / risk_scoring / ip_service / jpo_client /
  audit_anchor / sentinel_* / rls / access_control / …`
- モデル（`backend/app/models/`、24+）: `contract / clause / change_order / dispute /
  payment_record / partner / legal_hold / retention / risk_item / workflow /
  knowledge_article / contract_template / case_access / notification / audit_log /
  audit_anchor / ip_asset / ip_document / ip_watch / user / department /
  attachment / comment / security_settings / app_settings / …`
- Migration: `backend/alembic/versions/` `001_initial … 009_ip_management`（+ `009_ai_provider_deepseek`）
- 検証実績: backend pytest 1,113 passed / 2 skipped（SQLite 全件＋PG 統合）、ruff / mypy clean、
  frontend typecheck / lint / Jest 43 passed、CI 8 ジョブ（backend / frontend / security / deploy は手動）
- 稼働環境: MVP `https://legalops-mvp.mirai-dx-platform.com`（ダミーデータ投入済み）。
  本番は人間ゲート待ち: Vault secrets（#23）・CSP enforce（#24）・CF/Neon 本番構築（#50）

### 2.3 既に存在する関連機能（重複除去の前提）

| 領域 | 既存実装 |
| --- | --- |
| 電子契約 | プレイブックで「クラウドサイン等 API 連携は **将来拡張**・当面 PDF＋電子印鑑＋メール往復が正本」と明記（`docs/legal_playbook.md`） |
| 全文／類似検索 | `similarity_search.py`＋migration `003_knowledge_articles_trgm`（pg_trgm）で部分実装 |
| 労務費 | 労務費・材料費・安全衛生経費・法定福利費・建退共・短工期・低見積りチェック実装済み（`compliance_checker` 等） |
| 取適法 | 支払コンプライアンス（`payment_compliance`）・適用法令判定（`applicable_law`）実装済み |
| 建設業法 | 19 条チェック・改正建設業法対応（Loop 80・PR #80） |
| 変更契約 | `change_order` model / service / UI 実装済み |
| 紛争 | `dispute` model / service / Timeline 実装済み |
| 協力会社 | `partner` model / service（台帳・建設業許可・CCUS 等） |
| 知財 | `ip_*` model / `jpo_client`（JPO API・デモモード）・台帳 / ウォッチ / 書類 AI 解析（PR #94） |
| 法令改正影響 | `law_change_impact`＋`backend/data/law_changes`（法令改正マニフェスト管理） |
| RAG | `legal_rag` / `evidence_lookup`（一次情報 RAG・引用リンク） |
| RLS / ACL / 監査 | `rls` / `access_control` / `audit_*`（RLS 13 テーブル・案件単位 ACL・WORM・追記専用） |
| Legal Hold / Retention | `legal_hold_service` / `retention_service`（WORM・保存期間・fail-closed） |
| ワークフロー / 通知 | `workflow_engine` / `notification_service`（稟議・承認・エスカレーション） |

---

## 3. 目標像と設計原則

### 3.1 目標像

```text
Construction-LegalOps-DX
 = 建設業CLM            （契約ライフサイクル完備）
 + Legal Matter Management（契約を越えた法務案件管理）
 + Construction Compliance（労務費・取適法・公共工事・JV・協力会社）
 + Regulatory Intelligence（法令改正ウォッチ→影響分析）
 + AI Legal Agent       （分野別 Skill 群・相互検証・人間最終判断）
```

### 3.2 設計原則（変更不可）

1. **AI に最終法的判断をさせない**（README・AGENTS 方針を維持）。期限・支払日等の確定計算は
   ルールエンジンで行い、AI は抽出・分類・説明・要約に限定する。
2. 既存の **RLS / 案件 ACL / 倫理壁 / Legal Hold / WORM / 監査ログ / 追記専用** 基盤を
   新機能（Matter / 内部通報 / Evidence 等）にもそのまま適用する。
3. 電子契約は「PDF 送信」ではなく、建設業法 19 条・取適法に基づく **承諾証跡（電磁的方法の
   承諾記録）を持った機能** として設計する（相手方承諾の要件）。
4. Compliance ルールは静的ルールでなく **更新型 Compliance Engine**（労務費基準等は国交省が更新継続中）。
5. 外部 API（CloudSign / DocuSign / e-Gov / 国交省 / 公取委 / JPO 等）はデモモード既定・
   fail-closed とし、実接続は人間の資格情報ゲート後とする（既存 `JPO_API_MODE=demo` の方式に倣う）。
6. 法務システムは AI 精度以前に **DB の正しさが命**。マスタ正規化・重複検知・
   Metadata Completeness を前提機能とする。

---

## 4. 最優先 15 機能

| 優先 | 追加機能 | 推奨 |
| -- | --- | --: |
| 1 | 電子契約・電子署名連携 | 🔴 P0 |
| 2 | 契約交渉・Redline 管理 | 🔴 P0 |
| 3 | 契約義務・履行条件管理 | 🔴 P0 |
| 4 | 労務費基準・見積書チェック高度化 | 🔴 P0 |
| 5 | 契約書全文検索＋類似契約検索 | 🔴 P0 |
| 6 | 法令改正自動ウォッチ | 🔴 P0 |
| 7 | Legal Matter／案件管理 | 🔴 P0 |
| 8 | 顧問弁護士依頼・回答管理 | 🔴 P0 |
| 9 | 入札・独禁法・談合コンプライアンス | 🔴 P0 |
| 10 | 公共工事契約・発注者別ルール管理 | 🔴 P0 |
| 11 | JV 契約・共同企業体管理 | 🟠 P1 |
| 12 | 協力会社ポータル | 🟠 P1 |
| 13 | 証拠・クレーム時系列自動生成 | 🟠 P1 |
| 14 | 法務 AI Agent＋専門 Skills | 🟠 P1 |
| 15 | 経営向け Legal Risk Dashboard | 🟠 P1 |

---

## 5. 拡張機能カタログ（272 候補・グループ別）

各候補には固定番号（1〜272）を振る。後続フェーズ計画・Issue はこの番号で参照する。

### 5.1 契約ライフサイクル完成（#1〜15）— 🔴 Phase 1

| # | 機能 | 優先 |
| - | --- | -: |
| 1 | 電子契約連携（CloudSign / DocuSign 等） | P0 |
| 2 | 電子署名ステータス管理（未送信→送信→閲覧→署名→締結） | P0 |
| 3 | 電子契約同意証跡管理（電磁的方法の承諾記録） | P0 |
| 4 | 締結済み文書自動取込（電子契約→正本保管へ自動登録） | P0 |
| 5 | Redline 管理（Word/PDF 修正履歴を条項単位比較） | P0 |
| 6 | 交渉履歴管理（誰が何を要求・譲歩したか記録） | P0 |
| 7 | 条項ステータス（Accepted / Rejected / Negotiating） | P1 |
| 8 | 条項オーナー管理（法務・工事・営業・購買等へ担当割当） | P1 |
| 9 | 契約義務管理（報告・通知・提出・保険・更新等） | P0 |
| 10 | Obligations Calendar（契約義務を期限カレンダー化） | P0 |
| 11 | 条件成就管理（契約発効条件・支払条件等） | P1 |
| 12 | 自動更新判定（自動更新／解約通知期限の管理） | P1 |
| 13 | 契約終了チェック（精算・返却・秘密保持・保証残存確認） | P1 |
| 14 | 契約関係図（原契約→変更→覚書→発注書の親子関係） | P1 |
| 15 | 契約データルーム（案件単位で全関連書類を束ねる） | P1 |

### 5.2 労務費基準・見積書チェック高度化（#16〜28）— 🔴 Phase 2

| # | 機能 | 優先 |
| - | --- | -: |
| 16 | 労務費基準 API／データ更新（国交省基準値の更新取込） | P0 |
| 17 | 工種別基準値管理（とび・土工・舗装・解体等） | P0 |
| 18 | 都道府県別比較 | P0 |
| 19 | 見積書自動分解（労務費・材料費等を構造化抽出） | P0 |
| 20 | 労務費乖離率（基準との差を自動計算） | P0 |
| 21 | ダンピング警告（著しく低い見積りを検出） | P0 |
| 22 | 短工期判定（標準的工期との差を警告） | P0 |
| 23 | 見積変更要求監視（不当に低い変更要求の検出） | P1 |
| 24 | 価格協議履歴（協議申出・回答・理由を証跡化） | P0 |
| 25 | スライド条項管理（資材・労務費変動による変更） | P1 |
| 26 | 価格転嫁シミュレータ | P1 |
| 27 | 見積書様式生成（国交省様式に沿った出力） | P1 |
| 28 | コミットメント条項管理（労務費・賃金関連の表明管理） | P1 |

> 背景: 2025-12 改正の標準請負契約約款（材料費・労務費・安全衛生経費・建退共掛金等の内訳追加・
> 価格変動時の契約変更協議）と、更新が続く労務費基準（国交省ポータル）に対応するため。

### 5.3 取適法対応の高度化（#29〜40）

| # | 機能 |
| - | --- |
| 29 | 発注日による旧法／新法自動切替 |
| 30 | 対象取引判定 Wizard |
| 31 | 資本金＋従業員数判定 |
| 32 | 委託類型自動分類 |
| 33 | 4 条明示事項チェック |
| 34 | 7 条記録自動生成 |
| 35 | 支払 60 日シミュレータ |
| 36 | 手形／電子記録債権判定 |
| 37 | 振込手数料負担チェック |
| 38 | 価格協議要請ログ |
| 39 | 協議拒否・未回答アラート |
| 40 | 取適法監査レポート |

> 既存 `payment_compliance` を拡張する形で実装（重複構築しない）。

### 5.4 公共工事特化（#41〜60）— 🔴 Phase 2（差別化領域）

| # | 機能 | 優先 |
| - | --- | -: |
| 41 | 発注機関マスタ | P0 |
| 42 | 発注機関別契約条件 | P0 |
| 43 | 公共工事標準請負約款差分チェック | P0 |
| 44 | 自治体独自約款管理 | P1 |
| 45 | 入札公告・仕様書取込 | P1 |
| 46 | 入札条件チェック | P1 |
| 47 | 入札参加資格期限管理 | P1 |
| 48 | 経審情報管理 | P1 |
| 49 | 指名停止情報管理 | P1 |
| 50 | 契約保証管理 | P1 |
| 51 | 前払金保証管理 | P1 |
| 52 | 履行保証期限管理 | P1 |
| 53 | e-BISC / GECS 等の連携 | P1 |
| 54 | 発注者通知期限管理 | P0 |
| 55 | 工期延伸協議管理 | P0 |
| 56 | スライド請求管理 | P0 |
| 57 | 設計変更協議管理 | P0 |
| 58 | 工事一時中止・再開記録 | P1 |
| 59 | 発注者との協議簿連携 | P1 |
| 60 | 公共工事別 Legal Dashboard | P1 |

### 5.5 JV・共同企業体管理（#61〜70）— 🟠 Phase 2

| # | 機能 |
| - | --- |
| 61 | JV 台帳 |
| 62 | JV 協定書管理 |
| 63 | 代表会社・構成員管理 |
| 64 | 出資比率管理 |
| 65 | 利益・損失分担管理 |
| 66 | 役割・権限マトリクス |
| 67 | JV 承認ルート |
| 68 | JV 契約差分 AI レビュー |
| 69 | JV 内紛争・請求管理 |
| 70 | JV 終了・清算管理 |

### 5.6 Legal Matter Management（#71〜84）— 🔴 Phase 1（最大級の追加候補）

| # | 機能 | 優先 |
| - | --- | -: |
| 71 | 法務案件台帳 | P0 |
| 72 | Matter ID 採番 | P0 |
| 73 | 法務相談→Matter 昇格 | P0 |
| 74 | 担当法務アサイン | P0 |
| 75 | 案件優先度 | P1 |
| 76 | 案件リスクランク | P1 |
| 77 | SLA 管理 | P1 |
| 78 | 案件タイムライン | P0 |
| 79 | 関係契約リンク | P0 |
| 80 | 関係会社リンク | P1 |
| 81 | 関連法令リンク | P1 |
| 82 | Legal Hold 連動 | P0 |
| 83 | 案件クロージングレビュー | P1 |
| 84 | Lessons Learned | P1 |

### 5.7 顧問弁護士・外部法律事務所管理（#85〜96）— 🔴 Phase 1

| # | 機能 |
| - | --- |
| 85 | 顧問弁護士依頼起票 |
| 86 | 法律事務所台帳 |
| 87 | 担当弁護士台帳 |
| 88 | 依頼内容・質問管理 |
| 89 | 回答書管理 |
| 90 | 回答期限管理 |
| 91 | 利益相反確認 |
| 92 | Confidential Matter 分類 |
| 93 | 外部弁護士費用管理 |
| 94 | 見積・請求管理 |
| 95 | 法律事務所別 KPI |
| 96 | 過去回答ナレッジ化 |

### 5.8 紛争・クレーム機能の高度化（#97〜112）— 🟠 Phase 3

| # | 機能 |
| - | --- |
| 97 | Claim Notice Generator |
| 98 | 通知期限自動判定 |
| 99 | Time Bar 警告 |
| 100 | Delay Event 台帳 |
| 101 | 原因別遅延分類 |
| 102 | 追加費用積上げ |
| 103 | 損害額計算 |
| 104 | EOT／工期延長管理 |
| 105 | 証拠充足度スコア |
| 106 | AI 証拠不足検知 |
| 107 | 写真・議事録・メール時系列統合 |
| 108 | Claim Chronology 自動生成 |
| 109 | 主張・反論マトリクス |
| 110 | 和解案比較 |
| 111 | 訴訟・ADR ステージ管理 |
| 112 | 消滅時効タイマー |

### 5.9 独禁法・入札談合・コンプライアンス（#113〜124）— 🔴 Phase 3（現状の空白）

| # | 機能 | 優先 |
| - | --- | -: |
| 113 | 独禁法チェック | P0 |
| 114 | 入札談合リスクチェック | P0 |
| 115 | 競合他社接触記録 | P0 |
| 116 | 会合・懇親会事前申請 | P1 |
| 117 | 価格情報交換禁止チェック | P0 |
| 118 | JV 形成時競争法チェック | P1 |
| 119 | 競合との共同研究チェック | P1 |
| 120 | 競争法 AI 相談 | P1 |
| 121 | 贈収賄・接待管理 | P1 |
| 122 | 公務員接触記録 | P1 |
| 123 | 寄付・協賛審査 | P2 |
| 124 | コンプライアンス研修履歴 | P1 |

### 5.10 内部通報・調査（#125〜135）— 🟠 Phase 3

| # | 機能 |
| - | --- |
| 125 | 内部通報受付 |
| 126 | 匿名通報 |
| 127 | 通報者情報隔離 |
| 128 | Investigative Matter 管理 |
| 129 | 調査担当者限定 ACL |
| 130 | 証拠保全 |
| 131 | ヒアリング記録 |
| 132 | 調査タイムライン |
| 133 | 是正措置管理 |
| 134 | 再発防止管理 |
| 135 | 経営報告匿名集計 |

> 既存の RLS・案件 ACL・Legal Hold 設計をそのまま活用できる（技術的親和性が高い）。

### 5.11 協力会社コンプライアンス（#136〜152）— 🟠 Phase 2

| # | 機能 |
| - | --- |
| 136 | 協力会社セルフ登録 |
| 137 | 建設業許可自動確認 |
| 138 | 許可更新期限 |
| 139 | 社会保険確認 |
| 140 | CCUS 確認 |
| 141 | 技術者資格確認 |
| 142 | 経審確認 |
| 143 | 反社チェック |
| 144 | 制裁リストチェック |
| 145 | 倒産リスク |
| 146 | 保険証券期限 |
| 147 | 安全成績 |
| 148 | 過去トラブル履歴 |
| 149 | 契約違反履歴 |
| 150 | Partner Risk Score |
| 151 | 定期再審査 |
| 152 | 協力会社ポータル |

### 5.12 法令・規制 Intelligence（#153〜167）— 🔴 Phase 4

| # | 機能 | 優先 |
| - | --- | -: |
| 153 | e-Gov 法令自動取得 | P0 |
| 154 | 国交省通知自動取得 | P0 |
| 155 | 公取委更新取得 | P0 |
| 156 | 法令 Version 管理 | P0 |
| 157 | 新旧対照表生成 | P0 |
| 158 | 施行日タイムライン | P0 |
| 159 | 自社契約への影響検索 | P0 |
| 160 | 影響案件一覧 | P0 |
| 161 | 影響度スコア | P1 |
| 162 | 改正文書自動要約 | P1 |
| 163 | 法務担当者レビュー | P0 |
| 164 | 対応タスク自動生成 | P1 |
| 165 | 社内規程改定候補 | P1 |
| 166 | ひな形改定候補 | P1 |
| 167 | 過去版追跡 | P1 |

> 既存 `law_change_impact`＋`backend/data/law_changes` のマニフェスト管理を、自動取得型へ拡張する。

### 5.13 AI Legal Agent（#168〜188）— 🟠 Phase 4

```text
Legal Orchestrator Agent
        │
        ├─ Contract Review Skill
        ├─ Construction Law Skill
        ├─ 取適法 Skill
        ├─ Public Works Skill
        ├─ Labor Cost Skill
        ├─ Claim Analysis Skill
        ├─ Partner Compliance Skill
        ├─ Competition Law Skill
        ├─ Regulatory Watch Skill
        └─ Evidence Verification Skill
```

| # | AI 機能 |
| - | --- |
| 168 | 契約レビュー Agent |
| 169 | 条項抽出 Agent |
| 170 | 不足条項 Agent |
| 171 | 建設業法 Agent |
| 172 | 取適法 Agent |
| 173 | 公共工事 Agent |
| 174 | 労務費 Agent |
| 175 | クレーム分析 Agent |
| 176 | 証拠整理 Agent |
| 177 | 法令調査 Agent |
| 178 | 法令改正 Agent |
| 179 | 類似案件検索 Agent |
| 180 | 顧問弁護士依頼ドラフト Agent |
| 181 | 契約交渉論点 Agent |
| 182 | 経営向け要約 Agent |
| 183 | AI 相互レビュー |
| 184 | Confidence Score |
| 185 | Evidence Coverage Score |
| 186 | Hallucination Guard |
| 187 | 出典切れチェック |
| 188 | AI 結果差分管理 |

### 5.14 Legal Knowledge Management（#189〜203）

| # | 機能 |
| - | --- |
| 189 | 法務 FAQ |
| 190 | 法務判断事例 DB |
| 191 | 顧問弁護士回答 DB |
| 192 | 過去交渉事例 DB |
| 193 | 条項 Playbook |
| 194 | 条項許容レンジ |
| 195 | 原則 NG 条項 |
| 196 | 条件付き許容条項 |
| 197 | 部門別ガイド |
| 198 | 契約種別別ガイド |
| 199 | 法務判断理由保存 |
| 200 | Knowledge Quality Score |
| 201 | 重複ナレッジ統合 |
| 202 | 有効期限・再レビュー |
| 203 | 廃止ナレッジ管理 |

### 5.15 AI を使った契約インテリジェンス（#204〜216）— 🟠 Phase 4

| # | 機能 |
| - | --- |
| 204 | Clause Analytics |
| 205 | 条項採用率 |
| 206 | 相手先別譲歩傾向 |
| 207 | 部門別リスク傾向 |
| 208 | 契約期間分析 |
| 209 | 損害賠償上限分析 |
| 210 | 保証期間分析 |
| 211 | 契約不適合責任分析 |
| 212 | 支払条件分析 |
| 213 | 自動更新分析 |
| 214 | 解約条件分析 |
| 215 | 契約交渉期間分析 |
| 216 | 契約レビュー工数分析 |

### 5.16 経営向け Legal Dashboard（KPI 定義）

```text
全契約 → AI/ルール → Legal Risk Intelligence → 経営Dashboard
```

| KPI |
| --- |
| 契約総額 |
| High Risk 契約額 |
| 紛争 Exposure |
| 変更契約累積額 |
| 未処理クレーム額 |
| 支払遅延リスク |
| 労務費 Compliance |
| 協力会社 High Risk |
| 法務審査滞留 |
| 顧問弁護士案件 |
| 重大法令改正 |
| 期限超過 |
| Legal Hold 案件 |
| 部門別リスク |
| 発注者別リスク |

### 5.17 証拠・eDiscovery（#217〜230）— 🟠 Phase 3

| # | 機能 |
| - | --- |
| 217 | Evidence Repository |
| 218 | Evidence ID 採番 |
| 219 | SHA-256 証拠ハッシュ |
| 220 | Chain of Custody |
| 221 | 収集者記録 |
| 222 | 収集日時 |
| 223 | 証拠閲覧履歴 |
| 224 | 証拠 Export |
| 225 | 重複ファイル検出 |
| 226 | メール証拠取込 |
| 227 | 写真 EXIF 保持 |
| 228 | 証拠タイムライン |
| 229 | 証拠関連性 AI 分類 |
| 230 | Legal Hold 解除承認 |

### 5.18 API・他システム統合（#231〜245）

| # | 機能 |
| - | --- |
| 231 | External REST API |
| 232 | Webhook |
| 233 | API Key 管理 |
| 234 | OAuth Client 管理 |
| 235 | Integration Audit |
| 236 | SharePoint 同期（※`sharepoint_service` 既存 → 拡張） |
| 237 | Exchange メール取込 |
| 238 | Teams 通知 |
| 239 | DeskNet's NEO 連携 |
| 240 | DirectCloud 連携 |
| 241 | ERP/会計連携 |
| 242 | 工事管理システム連携 |
| 243 | 購買システム連携 |
| 244 | 電子契約連携 |
| 245 | JPO 連携（※既存 `jpo_client` あり → 拡張） |

### 5.19 セキュリティ・AI Governance（#246〜260）

| # | 機能 |
| - | --- |
| 246 | 権限定期棚卸 |
| 247 | SoD チェック |
| 248 | 権限申請・承認 |
| 249 | Temporary Access |
| 250 | Break Glass |
| 251 | AI モデル Allowlist |
| 252 | AI API 予算上限 |
| 253 | AI Token Cost Dashboard |
| 254 | AI Prompt Registry |
| 255 | Prompt Version 管理 |
| 256 | AI Input Classification |
| 257 | External AI 送信判定 |
| 258 | PII 自動 Masking |
| 259 | AI Output Approval |
| 260 | AI Incident 管理 |

### 5.20 データ品質（#261〜272）

| # | 機能 |
| - | --- |
| 261 | Master Data Hub |
| 262 | 法人名正規化 |
| 263 | 発注者名正規化 |
| 264 | 契約種別正規化（※migration 008 で正準値化済み → 継続監視へ） |
| 265 | 法令名正規化 |
| 266 | 契約番号重複検知 |
| 267 | 不完全データ検出 |
| 268 | Metadata Completeness Score |
| 269 | Duplicate Contract Detection |
| 270 | AI 抽出値 Confidence |
| 271 | 人間修正履歴 |
| 272 | Data Lineage |

---

## 6. 知財（IP）機能の整理方針

`Civil-Technology-IP-Intelligence-Platform` を知財の正本とする場合は以下で分離する
（LegalOps 側で特許検索エンジンを巨大化しない）。

```text
Construction-LegalOps-DX
        │  ライセンス契約 / NDA / 共同研究契約 / 知財紛争
        ▼
Civil-Technology-IP-Intelligence-Platform
        ├─ JPO / 特許検索 / 競合分析 / 出願ウォッチ
        ├─ Patent Landscape
        └─ AI 技術比較
```

> 判断要: 現状の `ip_*`（知財台帳・ウォッチ・書類 AI 解析・JPO demo client）を LegalOps に残すか、
> 正本側へ移すかは経営判断（本ロードマップでは LegalOps 内は契約系 IP（ライセンス/NDA/共同研究）に
> 限定する方向を推奨）。

---

## 7. 推奨する最終左メニュー（アコーディオン再編）

```text
🏠 ホーム        ダッシュボード / My Task / 通知 / Legal Risk
📑 契約          契約台帳 / 契約レビュー / 契約申請 / 承認 / 契約交渉 / 電子締結 / 契約義務 / 期限・更新 / 変更契約
🏗 建設法務      建設業法 / 労務費基準 / 取適法 / 公共工事 / JV / 支払・検収 / 施工体制
🏢 取引先        協力会社台帳 / 許可・資格 / CCUS / 反社 / Partner Risk
⚖️ 法務案件      法務相談 / Matter / 顧問弁護士 / 紛争 / クレーム / 債権 / Legal Hold
🛡 コンプライアンス コンプライアンスチェック / 独禁法・談合 / 贈収賄 / 内部通報 / 調査案件
📚 Legal Intelligence  法令 / 法令改正 / ナレッジ / 条項Playbook / 類似契約 / AI法務Agent
📊 分析          契約分析 / Legal Risk / クレームExposure / Compliance / 経営レポート
🧾 証跡・監査    証拠 / 監査ログ / AI監査 / Data Retention
⚙️ 管理          ユーザー / 権限 / ワークフロー / マスタ / AI / API / 外部連携 / システム設定
```

---

## 8. 開発順序（Phase 1〜5）

### Phase 1: LegalOps 完成（🔴 先行実装）

```text
電子契約 → Redline → Obligations → 全文/類似検索 → Matter → 顧問弁護士管理
```

- スコープ: カタログ #1〜15（うち P0 は #1-6・9-10）、#71-84（P0: 71-74・78-79・82）、#85-96
- 参照: §9 の Phase 1 Issue（#97〜#102 相当）
- 完了条件（DoD）: 各 Issue の Completion Criteria 充足＋backend pytest / ruff / mypy・
  frontend typecheck / lint / Jest 全緑＋監査ログ・RLS/ACL 適用

### Phase 2: 建設業特化を完成（🔴 / 🟠）

```text
労務費基準更新 → 公共工事 → JV → 施工体制 → 協力会社Portal
```

- スコープ: #16-28・#41-60・#61-70・#136-152
- DoD: 更新型 Compliance Engine（データ取込 1 系統以上をデモモードで実証）＋公共工事ダッシュボード

### Phase 3: リスク統制（🔴 / 🟠）

```text
独禁法/談合 → 内部通報 → Investigation → Evidence/eDiscovery
```

- スコープ: #113-124・#125-135・#217-230・#97-112（紛争高度化）
- DoD: 通報者情報隔離（RLS 分離）＋Evidence ハッシュ/Chain of Custody 実装

### Phase 4: AI-native 化（🟠）

```text
Legal Agent → Regulatory Watch → Clause Intelligence → AI相互検証
```

- スコープ: #153-167・#168-188・#204-216
- DoD: Orchestrator＋Skill 2 本以上＋Confidence/Evidence Coverage/Hallucination Guard

### Phase 5: 経営基盤化（🟠）

```text
Legal Risk Intelligence → Exposure → KPI → 経営判断支援
```

- スコープ: §5.16 KPI 群（全カテゴリを集計する Dashboard）
- DoD: 経営レポートに KPI 15 項目を実データで表示

> 参照: §5 の「既に実装済み」注記は重複構築しない。既存 `similarity_search`（trgm）、
> `law_change_impact`、`payment_compliance`、`sharepoint_service`、`ip_service/jpo_client` を拡張する。

---

## 9. GitHub Issue 化計画（Issue 駆動開発・AGENTS §14 準拠）

Phase 1 は次の 6 Issue に分解し、各 Issue に Completion Criteria・影響範囲・検証方法を記載する
（作成済み Issue 番号は各 Issue 参照）。

| Issue | タイトル（案） | 対象カタログ | 備考 |
| --- | --- | --- | --- |
| E-1 | 電子契約・電子署名ステータス管理（承諾証跡対応） | #1-4 | CloudSign/DocuSign はデモモード＋アダプタ IF |
| E-2 | 契約交渉・Redline 管理 | #5-8 | 条項単位ステータス（既存 `clause` 拡張） |
| E-3 | 契約義務・Obligations Calendar | #9-13 | 期限カレンダーはルールエンジンで算出 |
| E-4 | 契約全文検索・類似契約検索の製品化 | #5（下位） | 既存 trgm / similarity_search を UI まで |
| E-5 | Legal Matter Management（Matter 台帳・昇格・Legal Hold 連動） | #71-84 | 案件 ACL は既存基盤を流用 |
| E-6 | 顧問弁護士依頼・回答管理 | #85-96 | 外部アクセス ACL（既存設計）を前提 |

---

## 10. ヒューマンゲート・外部依存・リスク

| 区分 | 内容 |
| --- | --- |
| 本番リリース | 人間ゲート継続（#23 Vault secrets・#24 CSP enforce・#50 CF/Neon 本番）。release 期限 2026-11-16 |
| 電子契約 API | CloudSign / DocuSign のアカウント・API 資格情報（デモモードで先行開発・fail-closed） |
| 労務費基準データ | 国交省ポータルの公開形式（PDF/Excel 等）に応じた取込設計が必要 |
| 法令データ | e-Gov / 公取委の公開 API・更新頻度調査が必要 |
| 知財正本の分離 | `Civil-Technology-IP-Intelligence-Platform` との役割分担は経営判断 |
| 外部システム連携 | NEO / DirectCloud / ERP / 工事管理システムの API 仕様は要確認（ヒアリング必須） |
| リソース | Phase 全実施は複数 PR・複数ループを要する。本ロードマップの通り順次 Issue 化して実装する |

---

## 11. 文書管理

- 正本: 本ファイル。フェーズ完了・スコープ変更時は必ず更新し、CHANGELOG / README と整合させる。
- 関連文書: `docs/legal_playbook.md`（電子契約の将来拡張注記・本計画で更新対象）、
  `docs/requirements.md`、`docs/EVALUATION_IMPROVEMENT_REPORT_2026-08-12.md`、
  `docs/MVP_ASSESSMENT_2026-08-14.md`、`README.md`
