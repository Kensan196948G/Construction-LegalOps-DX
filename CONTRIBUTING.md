# コントリビューションガイド

Construction-LegalOps-DX への貢献ありがとうございます。本書は開発フロー・コミット規約・PR 運用を定めます。
**社内法務領域を扱うため、品質・セキュリティ・人間レビューを最優先**としてください。

---

## 1. 開発の前提

- 6 ヶ月固定スコープの社内プロジェクトです。リリース期限は登録日 +6 ヶ月（厳守）。
- `Monitor → Build → Verify → Improve` のループサイクルで運用します。
- AI レビュー（Codex / CodeRabbit）+ 人間レビューの二重チェックを必須とします。

## 2. ブランチ命名規約

`main` を保護ブランチとし、以下のプレフィックスを使用してください。

| プレフィックス | 用途 | 例 |
|----------------|------|-----|
| `feature/`     | 新規機能 | `feature/contract-list-api` |
| `fix/`         | バグ修正 | `fix/login-redirect-loop` |
| `docs/`        | ドキュメント変更のみ | `docs/update-readme-stack` |
| `refactor/`    | 挙動を変えないリファクタ | `refactor/auth-service` |
| `test/`        | テスト追加・修正 | `test/contract-repository` |
| `chore/`       | ビルド・CI・依存更新 | `chore/bump-fastapi-0.115` |
| `security/`    | セキュリティ対応 | `security/patch-cve-2026-xxxx` |

- ブランチ名は kebab-case、簡潔に。
- 関連 Issue 番号を含めると追跡しやすいです（例: `feature/123-contract-list`）。

## 3. コミットメッセージ規約（Conventional Commits）

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **type**: `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert` / `security`
- **scope**: 影響範囲（例: `backend`, `frontend`, `infra`, `auth`, `contracts`）
- **subject**: 50 文字程度、命令形、末尾ピリオドなし
- **body**: 「なぜ」を中心に記述（任意）
- **footer**: `BREAKING CHANGE:` / `Refs: #123` / `Co-Authored-By:` など

例:

```
feat(contracts): 契約書一覧の期限フィルタを追加

期限切れ間近の契約書のみ抽出できるよう、API クエリパラメータと
フロントのフィルタ UI を追加。

Refs: #42
```

## 4. PR テンプレート

PR 本文には最低限以下のセクションを含めてください。

```markdown
## 概要
（変更内容を 1〜3 行で）

## 変更点
- ...
- ...

## 動作確認 / Test Plan
- [ ] backend: `pytest` 緑
- [ ] frontend: `npm test` 緑
- [ ] 手動: 〇〇画面で △△ が表示されること

## レビュー観点
- セキュリティ影響: あり / なし
- スキーマ変更: あり / なし
- 監査ログ影響: あり / なし

## 関連 Issue / Goal
Refs: #
```

## 5. レビュー基準

### 5.1 自動レビュー（必須）

- **Codex review** (`/codex:review`) と **CodeRabbit** (`/coderabbit:review`) を両方実行。
- 認証・認可・DB スキーマ・並列処理の変更時は **Codex 対抗レビュー** (`/codex:adversarial-review`) を追加で実施。
- Critical / High 指摘は **同一 PR 内で必ず解消** してからマージ。
- Medium 以下は Issue 化して次ループで対応可。

### 5.2 人間レビュー（必須）

- 最低 1 名の人間レビュアー承認が必要。
- **AI レビュー結果の人間確認は必須義務**: AI 出力は下書きであり、最終判断は人間レビュアーが行う。
- 法務・契約データに触れる変更は、法務担当者または PdM のレビューを推奨。

### 5.3 マージ要件

- すべての必須 CI ジョブが緑（backend / frontend / security / docker build）。
- AI Critical/High 解消済み。
- 人間承認 1 名以上。
- CHANGELOG.md 追記済み（ユーザ影響のある変更の場合）。
- マージ方式は **Squash Merge** 推奨。

## 6. テスト要求

| 種別 | 要件 |
|------|------|
| 単体テスト | 新規ロジックには原則テスト追加。カバレッジ低下は理由を PR に明記。 |
| 結合テスト | API エンドポイント追加時は最低 1 ケース（正常系 + 主要異常系）。 |
| セキュリティ | 認証・認可変更は権限境界テスト必須。 |
| ドキュメント | 公開挙動を変える場合 README / docs を同 PR で更新。 |

ローカルでの最低限の検証:

```bash
# backend
cd backend && ruff check . && mypy app && pytest

# frontend
cd frontend && npm run lint && npm run typecheck && npm test
```

## 7. セキュリティ・コンプライアンス

- シークレットを絶対にコミットしない（`.env`, `*.pem`, `*.key` は `.gitignore` 済み）。
- 個人情報・契約相手方情報を含むデータをテストに直接含めない（マスキング必須）。
- Trivy / Bandit の Critical / High は必ず解消。
- 監査ログの仕様変更は法定保存要件（電子帳簿保存法・建設業法）を確認。

## 8. AI 利用上の遵守事項

- AI（Claude API）への入力データは、社内データガバナンス規程に従う。
- AI 出力は **必ず人間が確認** してからユーザに提示・採用する。
- 弁護士法第 72 条に抵触する用途には用いない。
- プロンプト・モデル・応答メタデータは監査ログに記録する。

## 9. 質問・連絡

- 仕様の不明点は Issue で起票し、`question` ラベルを付与してください。
- 緊急のセキュリティ事項は公開 Issue ではなく社内チャネル経由で連絡してください。

ご協力ありがとうございます。
