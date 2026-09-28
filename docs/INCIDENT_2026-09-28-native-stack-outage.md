# 🔥 障害報告 / Deep Debug 記録 — 2026-09-28

> 対象: Construction-LegalOps-DX（native systemd stack: prod 8011/3011/8410, mvp 8013/3013/8412）
> 実施: Deep Debug Round 1〜3（Evidence ベース）
> 結論: **本番/MVP のアプリ層が全面停止していた（外部公開 URL も 500/502）。原因は 4 件の独立した欠陥。うち 3 件はコード/スクリプト側で恒久修正済み。残る復旧操作 1 件は特権操作のため人間ゲート。**

---

## 1. 影響（実測）

| 対象 | 障害発生時 | 現在 |
| --- | --- | --- |
| `legalops-prod-backend` (127.0.0.1:8011) | `inactive (dead)` / `status=203/EXEC`（2026-09-23 14:00:34 JST 以降） | 未復旧（人間ゲート） |
| `legalops-mvp-backend` (127.0.0.1:8013) | `inactive (dead)` / `status=203/EXEC`（2026-09-23 14:00:35 JST 以降） | 未復旧（人間ゲート） |
| `legalops-prod-frontend` (3011) | HTTP 500（`MODULE_NOT_FOUND`） | HTTP 307（`/login` へ正常リダイレクト） |
| `legalops-mvp-frontend` (3013) | HTTP 500（`MODULE_NOT_FOUND`） | HTTP 200 |
| `legalops-nginx` (8410 / 8412) | HTTP 500 / 500 | HTTP 307 / 200 |
| `https://legalops.mirai-dx-platform.com` | 302（Cloudflare Access challenge・正常） | 302（変化なし） |
| `https://legalops-mvp.mirai-dx-platform.com` | **HTTP 500（無認証で誰でも観測可能）** | HTTP 200 |
| `https://legalops-mvp.mirai-dx-platform.com/api/v1/ping` | HTTP 502 | 502（backend 未起動のため） |

障害は **2026-09-23 14:00 頃から約 5 日間**継続していた。MVP は Cloudflare Access 保護外のため、
外部から 500 が観測できる状態だった。

---

## 2. Root Cause（4 件・すべて実測で確定）

### RC-1【Critical】リポジトリ移設に systemd unit と venv shebang が追随していない

2026-09-23 にチェックアウトが
`/home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX`
→ `/home/kensan/Projects/Mirai-Admin-Platform/Construction-LegalOps-DX`
へ移動したが、以下は旧パスのままだった。

- `/etc/systemd/system/legalops-{prod,mvp}-{backend,frontend}.service` の `WorkingDirectory` / `ExecStart` / `PYTHONPATH`
- `backend/.venv/bin/uvicorn` の **shebang**（`#!/home/kensan/Projects/Mirai-DX-Project/.../backend/.venv/bin/python`）

Evidence:
- `systemctl status legalops-prod-backend` → `Main PID: 1964860 (code=exited, status=203/EXEC)`
  ※ `203/EXEC` は ExecStart の実体（shebang 含む）が解決できないことを示す。
- 実行中 frontend の journal:
  `Cannot find module '/home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX/frontend/.next/standalone/.next/server/middleware-manifest.json'`
- `diff infra/native/systemd/legalops-prod-backend.service /etc/systemd/system/legalops-prod-backend.service` → **IDENTICAL**
  ＝ リポジトリ側テンプレート自体が旧パスを保持しており、正規インストーラが旧パスを再配置していた（再発構造）。

### RC-2【High】Next.js standalone に `public/` と `.next/static/` が配置されていない

`next build` は `.next/standalone/` を作るが `public/` と `.next/static/` は複製しない
（`npm run start:standalone` が実施）。systemd unit は `node .next/standalone/server.js` を直接起動するため、
2026-09-06 15:30 の再ビルド以降この複製が欠けていた。

Evidence: `/` は 200 を返すが `/_next/static/**` と `/public/**` がすべて **404**（実測 6/6 と 3/3）。
Next.js は静的ファイルのルートを**起動時に登録する**ため、後からファイルを置いても稼働中プロセスは配信しない。

### RC-3【Critical】本番/MVP データベースが 17 マイグレーション遅延（40 テーブル欠落）

| DB | alembic | テーブル数 | コードが要求する head |
| --- | --- | --- | --- |
| `legalops_prod` | `009_ip_management` | 39 | `026_rls_restrictive_scope` |
| `legalops_mvp` | `009_ip_management` | 39 | `026_rls_restrictive_scope` |

`legalops_prod` に存在しないテーブル（40 件）: `esignature_envelopes` / `contract_obligations` /
`legal_matters` / `law_firms` / `labor_wage_standards` / `public_works_consultations` /
`joint_ventures` / `partner_reviews` / `labor_commitments` / `dispute_*` / `antitrust_*` /
`whistleblower_*` / `evidences` ほか。

＝ Phase 1〜3 の業務機能はコードは在るが**本番 DB にテーブルが無く、起動しても 500 になる状態**だった。
（backend が起動していなかったため表面化していなかった。）

### RC-4【Critical】依存未固定により CI が新規インストールで壊れる（SQLAlchemy 2.1 / greenlet）

`pyproject.toml` は `sqlalchemy>=2.0.36`（extra なし）で、ロックファイルも無い。
SQLAlchemy 2.0 は greenlet を必須依存としていたが、**2.1 で `extra == "asyncio"` へ移動**した。
そのため新規インストールでは greenlet が入らず、`sqlalchemy.ext.asyncio` の import が失敗する。

Evidence（実測・2026-09-28）:
- CI 相当の新規 venv: `sqlalchemy 2.1.1` / `alembic 1.20.0` / **greenlet なし**
- `alembic upgrade head` → `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed.`
- `pytest --collect-only` → `ModuleNotFoundError: No module named 'greenlet'`（1360 collected / 1 error）
- GitHub Actions: `Load Test (k6)` が 2026-09-27 に **"Apply migrations" ステップで failure**
  （`ci.yml` 最終成功は 2026-09-06 = SQLAlchemy 2.1.1 登場前。同一 main で再実行すれば backend / migrations ジョブも落ちる状態だった）
- ローカル既存 venv は `sqlalchemy 2.0.52` のため影響を受けず、差異が隠れていた

### 付随所見（High / Medium）

| # | 所見 | Evidence |
| --- | --- | --- |
| F-1 | **復元不能バックアップ**: PATH 先頭の `pg_dump` 17.10 で作った `-Fc` アーカイブを、唯一の `pg_restore` 16.14 が拒否 | `pg_restore: エラー: ファイルヘッダ内のバージョン(1.16)はサポートされていません` |
| F-2 | `/usr/bin/pg_dump` は Debian の `pg_wrapper`（Perl）で、**環境変数により報告バージョンが変わる** | `PGHOST/PGPORT` 設定時 `18.4` / 未設定時 `16.14`（同一バイナリ） |
| F-3 | frontend に **critical 1 + high 4** の脆弱性（`next` RCE ほか）。週次 Security スキャンが 3 週連続失敗 | `npm audit`: `next`（RCE, AVIF RCE）/ `sharp`（libheif）/ `js-yaml` / `browserslist` |
| F-4 | 週次 `Security (weekly deep scan)` が 2026-09-07 / 09-14 / 09-21 と 3 回連続 failure | `gh run list --workflow security.yml` |
| F-5 | `backend/dev_legalops.db`（SQLite 残骸）が残置。テスト基盤は PostgreSQL 単一化済み（#132） | ファイル存在 |
| F-6 | frontend の未使用 import による ESLint warning 3 件 | `npm run lint` |
| F-7 | `scripts/seed_demo_data.py` は CI の lint / type ゲート対象外（CI は `backend/` 内で `ruff check .` / `mypy app` を実行）。同ファイルは ruff 107 / mypy 39 の指摘を抱えたまま運用されている | `.github/workflows/ci.yml` の実行範囲 |
| F-8 | seed のカバレッジが Phase 3（migration 022〜025: dispute 高度化 / 独禁法 / 内部通報 / 証拠）に未対応。当該画面はデモ投入後も空のまま | seed 実行結果（`whistleblower_*` / `evidences` / `antitrust_*` が 0 件） |

> **確認して「問題なし」と判断した項目（誤検知の記録）**: seed `--delete` 実行時、
> `partner_reviews` と `labor_commitments` の削除件数が **0 と報告される**一方で実際には
> 削除されていた。当初これを報告件数の不具合と疑ったが、FK を実測したところ
> `partner_reviews.partner_id → partners ON DELETE CASCADE` および
> `labor_commitments.contract_id → contracts ON DELETE CASCADE` であり、
> 先に実行される親行（partners / contracts）の削除で **すでにカスケード削除済み**だった。
> 報告値 0 は正しい。**不具合ではない**（誤って不具合として報告しないよう記録する）。

---

## 3. 実施した修正

| # | 対象 | 内容 |
| --- | --- | --- |
| M-1 | ホスト | 旧パス → 新パスへの互換 symlink を作成（`~/Projects/Mirai-DX-Project/Construction-LegalOps-DX`）。既存の移設慣行（`AI-Structural-Engineering-Platform` 等）と同一方式。**緊急緩和**であり恒久対応は §4 |
| M-2 | `infra/native/install.sh` | unit を**インストール時に実パスへ描画**（`sed`）するよう変更。描画後に旧パスが残れば **fail-closed で拒否**。読み取り専用の `--check` モードを追加（実機で 6 unit の STALE を検出、exit 1） |
| M-3 | `scripts/stage_frontend_standalone.sh`（新規） | `next build` 後の staging を単一の権威に。`public/` と `.next/static/` を複製し、**BUILD_ID 一致・参照 chunk 全数・public 全数**を検証して fail-closed。`--verify` は書き込みなし |
| M-4 | `scripts/backup_db.sh` | サーバ major を検出し **同一 major の実バイナリ**（`/usr/lib/postgresql/<major>/bin/`）を選択。`pg_wrapper` の非決定性を回避。一致が無ければ**バックアップを書かずに失敗**。restore 側の `psql` も同様に固定 |
| M-5 | `backend/pyproject.toml` | `sqlalchemy[asyncio]>=2.0.36` へ修正（RC-4 の恒久修正） |
| M-6 | `frontend/package.json` / lock | `next` 15.5.22→**15.5.26**（critical RCE 修正）、`sharp`→0.35.5、`js-yaml@3`→3.15.2 / `js-yaml@4`→4.3.2、`browserslist`→4.29.2、`baseline-browser-mapping`→2.11.x、`postcss-selector-parser`→6.1.4 |
| M-7 | `frontend/app/(authenticated)/joint-ventures/page-client.tsx` | 未使用 import 3 件を削除（ESLint warning 解消） |
| M-8 | `scripts/seed_demo_data.py` | `partner_reviews` の冪等性を修正（同一協力会社・同一タイトルが既にあれば再投入しない）。旧実装は無条件 `create_review` で、再実行のたびに 3 件ずつ重複していた（実測: 2 回目で +3 → 修正後は 3 件のまま） |
| M-9 | `scripts/scan_secrets.sh` | AI 設定 UI のキー形式プレースホルダが `sk-[A-Za-z0-9]{20,}` に一致し、**PR #89 以降 `pre_deploy_check.sh` の secret exposure scan が常に失敗**していた。`sk-x{16,}` を allowlist に追加（実鍵は引き続き検出されることを negative verification で確認） |

---

## 4. 検証（すべて実測）

### 4.1 アプリ層の復旧（symlink 効果）

| 検証 | 結果 |
| --- | --- |
| `curl 127.0.0.1:3013/`（mvp frontend） | **200**（10,514 bytes） |
| `curl 127.0.0.1:3011/`（prod frontend） | **307** → `/login?callbackUrl=...`（正常） |
| `curl 127.0.0.1:8412/` / `8410/` | **200** / **307** |
| `curl https://legalops-mvp.mirai-dx-platform.com/` | **200** |

### 4.2 静的資産（M-3 の前提）

- staging 実施後: `--verify` → `OK: staged 93 js chunks (BUILD_ID 0FPvd_JLeymW7SJ7sUxui)`（exit 0）
- ただし稼働中プロセスの再起動までは 404 が続く（§5 の人間ゲート）

### 4.3 データベース移行（RC-3）— 実データでのドリル

本番 `legalops_prod` のバックアップを隔離 DB（`legalops_upgrade_drill`）へ復元し、その上で移行を実施。

| 段階 | alembic | テーブル | contracts | users | departments | audit_logs |
| --- | --- | --- | --- | --- | --- | --- |
| 復元直後（=本番と同一） | `009_ip_management` | 39 | 22 | 2 | 6 | 5 |
| `upgrade head` 後 | `026_rls_restrictive_scope` | 80 | **22** | **2** | **6** | **5** |
| `upgrade head` 再実行（冪等） | 変化なし | — | — | — | — | — |
| `downgrade 009_ip_management` | `009_ip_management` | 39 | **22** | **2** | — | — |

- 所有者は全 80 テーブルが `legalops_prod`（本番と同一）
- モデル定義との差分: **無し**（drill の 80 = モデル 79 + `alembic_version`）
- RLS: 12 ポリシーが `permissive=RESTRICTIVE` へ正しく変更
- 新規テーブル作成時刻の所有者: `esignature_envelopes` / `legal_matters` / `whistleblower_reports` / `evidences` / `joint_ventures` / `contract_obligations` = `legalops_prod`

### 4.4 実ランタイム検証（移行後 DB・別ポート 8099 の検証インスタンス）

`/healthz` → `{"status":"ok"}`、`/readyz` → `{"status":"ready","db":"ok"}`

主要業務 Flow（書き込み→読み戻し）**11/11 成功**:

```
[201] Matter作成 → [200] 取得 → [200] 状態変更 → [200] イベント
[201] 労務費基準作成 → [200] latest 取得
[201] JV作成 → [200] 取得
[201] 独禁法チェック作成
[201] 契約義務作成 → [200] 完了 → [200] 一覧
[200] 監査ログ / ダッシュボード
```

- 既存データ参照: `/api/v1/contracts` が本番由来の 22 件を返す
- 新規書き込み: `legal_matters=1` `matter_events=2` `joint_ventures=1` `contract_obligations=1`
  `labor_wage_standards=1` `antitrust_checks=1`
- 監査証跡: `audit_logs` 13 件（`matter.create` / `matter.status` / `jv.create` / `obligation.create` /
  `obligation.complete` / `labor_wage.create` / `antitrust_check.run` / `compliance.run` / `user.jit_provision` …）
- RBAC: role claim なしのトークンでは保護 API が **403**
- **既存契約 22 件は移行後も無傷**

### 4.5 テストスイート

| 対象 | 条件 | 結果 |
| --- | --- | --- |
| backend pytest | 実 PostgreSQL 16 / 既存 venv | **1375 passed** |
| backend pytest | 実 PostgreSQL 16 / **最新依存（SQLAlchemy 2.1.1）+ M-5 修正** | **1375 passed** |
| alembic upgrade head | 空 DB / 最新依存 + M-5 | **exit 0** → 80 テーブル / head `026` |
| frontend tsc | — | exit 0 |
| frontend lint | M-7 後 | exit 0（**warning 0**） |
| frontend jest | 25 suites | **98 passed** |
| frontend `next build` | 隔離環境 / **Next 15.5.26** | **exit 0**（全 30 route 生成） |
| frontend E2E (Playwright) | 隔離環境 / **Next 15.5.26** | **58 passed**（1.1 分） |
| `npm audit --audit-level=high` | M-6 後 | **0 vulnerabilities**（修正前: critical 1 + high 4 + moderate 1 + low 1） |
| backup → restore | M-4 | 0 error / 80 テーブル復元 / sha256 OK |
| `infra/native/install.sh --check` | 実機 | STALE 6 件 / OK 3 件 / **exit 1**（fail-closed） |
| unit レンダリング | `sed` 後の残存判定 | 9 unit すべて旧パス残存なし |

> **注（自己検証で発見した自分のバグ）**: M-2 の当初実装は残存判定に
> `grep -Eq "$STALE_ROOT_RE"` を使っており、この正規表現が**正しいパスにも一致**するため
> 常に install を拒否してしまう状態だった。レンダリング結果を実際に検査する試験を書いたことで
> 検出し、抽出結果を `$REPO` と完全一致比較（`grep -vxF`）する方式へ修正した。
> 「実装した」ではなく「実装が意図どおり動くことを実測した」ことの重要性を示す例。

### 4.6 使い捨て資源

検証に使用した `legalops_upgrade_drill` / `legalops_ci_fresh` / `legalops_ci_repro` /
`legalops_ci_fixed` / `legalops_restore_drill` および `/tmp/ci-repro-venv*` は**本番と無関係の隔離資源**。
`legalops_prod` / `legalops_mvp` への**書き込みは一切行っていない**（読み取りとバックアップのみ）。

---

## 5. 残る人間ゲート（特権操作・1 件）

本セッションのポリシーゲートは `systemctl start|stop|restart` を **INFRA_CHANGE(critical=常時拒否)**、
`.github/workflows/**` および `**/systemd/**` への書き込みを **DEPLOY / INFRA_CHANGE(critical=常時拒否)** として
拒否する。また `/etc` は **読み取り専用マウント**（`ro,nosuid,relatime`）で `sudo` も使用不可。
したがって以下は実行できず、**人間（root）作業**として残る。

### 5.1 アプリ層の復旧（RC-1 / RC-2 の解消）

```bash
# 1) unit をこのチェックアウトのパスで再描画してインストール（旧パスは描画時に置換される）
cd /home/kensan/Projects/Mirai-Admin-Platform/Construction-LegalOps-DX
sudo bash infra/native/install.sh --check   # 事前確認（読み取り専用。STALE が 6 件出るのが現状）
sudo bash infra/native/install.sh           # unit 再配置 + app tier 再起動 + health 確認

# 2) 正常性の確認（install.sh 内でも実施される）
curl -fsS http://127.0.0.1:8011/healthz
curl -fsS http://127.0.0.1:8013/healthz
curl -fsS http://127.0.0.1:3011/api/health
curl -fsS http://127.0.0.1:3013/api/health
```

> ⚠️ **`npm run build` を単独で実行しないこと。** 実行した場合は必ず
> `bash scripts/stage_frontend_standalone.sh` を続けて実行し、その後 frontend unit を再起動する。
> staging を忘れると RC-2 が再発する（HTML 200 / 資産 404）。

### 5.2 データベース移行（RC-3 の解消）

```bash
# 事前バックアップ（スクリプトがサーバ major と一致する pg_dump を自動選択する）
cd /home/kensan/Projects/Mirai-Admin-Platform/Construction-LegalOps-DX
BACKUP_DIR=/var/backups/legalops POSTGRES_USER=legalops_prod POSTGRES_DB=legalops_prod \
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 PGPASSWORD="$(...)" bash scripts/backup_db.sh

# 移行（ロール権限が必要。§4.3 のドリルで 009→026 は冪等・可逆・データ保全を実証済み）
# DSN は systemd と同じ EnvironmentFile から取る（リポジトリ・ログに DSN を書かない）。
# 1 つの DB を移行している間、他方のサービスは稼働したままでよい。
cd backend
set -a; . /etc/legalops/prod-backend.env; set +a   # DB_URL / JWT_SECRET 等を供給
APP_ENV=production alembic upgrade head

# legalops_mvp も同様（mvp-backend.env を使う）
set -a; . /etc/legalops/mvp-backend.env; set +a
APP_ENV=production alembic upgrade head

# 検証
psql -d legalops_prod -Atc "select version_num from alembic_version"   # 026_rls_restrictive_scope
psql -d legalops_prod -Atc "select count(*) from information_schema.tables where table_schema='public'"  # 80
psql -d legalops_prod -Atc "select count(*) from contracts"            # 22（不変であること）
```

### 5.3 セキュリティスキャンの再実行

```bash
gh workflow run security.yml --ref main
gh workflow run load-test.yml --ref main
```

---

## 6. Rollback

| 対象 | 手順 |
| --- | --- |
| 互換 symlink（M-1） | `rm /home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX`（unit を新パスへ描画済みなら不要。削除すると旧パス参照は再び壊れる点に注意） |
| unit（M-2） | `git checkout -- infra/native/install.sh` → `sudo bash infra/native/install.sh`（旧テンプレートのまま戻るため、旧パス symlink を維持すること） |
| DB 移行（RC-3） | `alembic downgrade 009_ip_management`（§4.3 で 009 へ戻しデータ保全を実証済み）。完全復旧は §5.2 のバックアップから `scripts/backup_db.sh --restore <file>` |
| 依存（M-5/M-6） | `git checkout -- backend/pyproject.toml frontend/package.json frontend/package-lock.json` → `pip install -e .[dev]` / `npm ci --legacy-peer-deps` **（セキュリティ修正が戻るため非推奨）** |
| staging（M-3） | 影響なし（追加のみ）。frontend unit 再起動で元の状態に戻る |

---

## 7. Lessons Learned（Memory へ保存すべき知見）

1. **絶対パスの焼き込みはチェックアウト移設で全 unit を同時に殺す。** unit はインストール時に描画し、
   残存すれば fail-closed にする（M-2）。移設時の互換 symlink は緩和策であって恒久策ではない。
2. **`next build` は standalone を再生成し、静的資産の staging を無効化する。** staging は単一の
   スクリプトに集約し、BUILD_ID と参照 chunk の全数一致で検証する（M-3）。
   Next.js は静的ルートを起動時に登録するため、稼働中プロセスは後置ファイルを配信しない。
3. **ロックファイルの無い `>=` 依存は CI を無音で壊す。** SQLAlchemy 2.1 の greenlet extra 化により、
   同一コミットの CI が日付だけで失敗するようになった。`sqlalchemy[asyncio]` を明示する（M-5）。
   定時ワークフローが唯一の検知手段だった＝ push 時 CI だけでは不十分。
4. **バックアップは「取得できた」ではなく「復元できた」で判定する。** クライアント major の混在
   （pg_dump 17/18 + pg_restore 16）はアーカイブを復元不能にする。`/usr/bin/pg_dump` は Debian の
   `pg_wrapper` であり `--version` が環境依存で変わるため、`/usr/lib/postgresql/<major>/bin/` を使う（M-4）。
5. **DB スキーマのドリフトはアプリ停止中は不可視。** 稼働監視は「プロセスが上がっているか」だけでなく
   `alembic_version` と期待 head の一致、および モデル定義とテーブル集合の一致まで見る必要がある。
6. **ポリシーゲート下では「復旧の最後の一手」が人間に残る。** unit 再描画（M-2）まで済ませてあるため、
   人間側は `sudo bash infra/native/install.sh` の 1 コマンドで復旧できる状態にして引き渡す。

---

## 8. 未実施・未確認（正直な記録）

- `legalops_prod` / `legalops_mvp` への**移行適用**（§5.2）。実データドリルで安全性は実証済みだが、
  RLS 権限変更を含むため承認ゲートとした。
- `systemctl` による**サービス再起動**（§5.1）。ポリシーゲートで拒否。
- frontend の**再ビルド**。稼働中の本番プロセスが同一 `.next/standalone` を参照しているため、
  無停止で再ビルドすると配信物が混在する危険があると判断し、分離ビルドでの検証に留めた。
- `Trivy (fs / config / secret)` と `Trivy (container image)` の失敗原因（ローカルに trivy が無く未再現）。
- Cloudflare Access / Tunnel の設定変更（DNS・Access は人間ゲート、Issue #50）。
- 本番 `Vault` secrets 投入（Issue #23）、CSP enforce 移行（Issue #24）。
