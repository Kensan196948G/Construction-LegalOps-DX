# 📝 Session Handoff — 本番デプロイ完了 (2026-07-20)

## 🎯 結論

**https://legalops.mirai-dx-platform.com が Cloudflare Access 配下で本番稼働開始。** v0.1.12 (PR #58/#59/#61/#62)。

## ✅ 検証 (全 PASS)

- DNS: `legalops` CNAME → tunnel `legalops-prod` (3e1bddee) / Cloudflare proxy
- Access 境界: 未認証 → Access ログイン 302 (winter-lake-f4c9.cloudflareaccess.com)
- Tunnel: 4 connections / Origin: /healthz ok・/readyz db=ok・nginx→backend 200
- DB: Neon main (ap-southeast-1, ssl=require, alembic head=005)
- スタック: prod overlay backend×2 + frontend×2 + celery×2・全 healthy・fail-closed ガード通過 (起動エラー 0)
- モード: APP_ENV=production / SSO_MODE=stub+EDGE_AUTH_BOUNDARY=cloudflare-access / SHAREPOINT=disabled / NOTIFY=disabled

## ⚠️ 実行中に検出・対処した事象

1. **CNAME 誤ルーティング**: apply スクリプトの `route dns <tunnel名>` が別 tunnel `a423aa88` に CNAME を作成 → UUID 明示 (`route dns 3e1bddee --overwrite-dns`) で修正。**apply スクリプトは tunnel 名でなく UUID を渡すべき (follow-up)**
2. **cloudflared が profile 未指定で未起動** → `--profile cloudflare-tunnel` を追加指定して起動
3. **preview URL が 502 化**: prod overlay が host :8410 を撤去したため。preview は「Phase 2 後削除可」の一時環境 (CLAUDE.md §33) のため想定内。host cloudflared (PID 2412097) の停止でクリーンに decommission 可

## 🚧 残課題

- **#63 (P1)**: Access JWT (Cf-Access-Jwt-Assertion) 検証 + 実 identity 導出 — 合成 stub 身分証の監査非追跡性を根治
- **#24**: CSP Report-Only → enforce (違反 0 件確認済み)
- CLAUDE_API_KEY 実値記入で AI レビュー有効化 (未記入時 fail-closed)
- 軽微: `/api/v1/health` の version が 0.1.0 のまま (hardcoded) / local postgres コンテナが未使用で稼働

## 🔧 再開時のポイント

- 本番スタック: `infra/docker/docker-compose.{yml,prod.yml,cloudflare-tunnel.yml}` + `.env.production` (mode 600・gitignore) を `--profile worker --profile cloudflare-tunnel` で up
- rollback: preview 構成の再 up / CNAME 削除 + connector 停止
- state.json に `production_deployment` レコード記録済み
