# 🌐 infra/cloudflare — Cloudflare Tunnel / Access 設定（IaC 雛形）

> **ステータス: 雛形（未適用）** — 適用には人間による Cloudflare API token 発行・DNS CNAME 作成が必要です（Issue #50 のアンブロック手順参照）。このディレクトリを置くだけでは何も起動・変更されません。

## 📌 構成

| ファイル | 役割 |
|---|---|
| `tunnel-config.example.yml` | cloudflared Tunnel のルーティング設定テンプレート（既存 nginx への ingress） |
| （将来）`access-policy.md` | Cloudflare Access のアプリ/ポリシー定義メモ（Entra ID IdP 連携） |

## 🚀 適用手順（人間 + CTO 協働、Issue #50 解除後）

1. 人間: Cloudflare ダッシュボードで Tunnel を作成し、トークンを取得（Zero Trust → Networks → Tunnels）
2. 人間: `legalops.mirai-dx-platform.com` の CNAME を Tunnel に向ける（Cloudflare が自動生成）
3. ホスト: `tunnel-config.example.yml` を実値でコピーし、cloudflared をサイドカーとして起動:

```bash
docker run -d --name cloudflared --network legalops_default \
  cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TUNNEL_TOKEN>
```

4. CTO: 動作確認後、cloudflared サービスを `docker-compose.prod.yml` へ正式追加する PR を作成

## 🔒 安全メモ

- Tunnel はアウトバウンド接続のみ（インバウンドポート開放不要）
- `<TUNNEL_TOKEN>` は Vault / ホストの env で管理し、リポジトリへコミットしない
- Access ポリシー適用までは Tunnel URL を有効化しない（認証境界の先行確立）
