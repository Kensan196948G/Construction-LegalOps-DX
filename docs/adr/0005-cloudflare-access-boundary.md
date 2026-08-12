# ADR 0005 — 本番認証境界を Cloudflare Access とする

- 状態: Accepted
- 決定日: 2026-07-20

## コンテキスト

本番 URL（legalops.mirai-dx-platform.com）は Cloudflare 経由で公開する。Entra ID SSO の完全投入前でも、
本番環境の未認証アクセスを遮断する境界が必要である。

## 決定

- 本番では Cloudflare Access（メール OTP + ルールグループ）を外部認証境界とする。
- バックエンドは `Cf-Access-Jwt-Assertion` を RS256 / issuer / aud で検証し、
  Access メールヘッダと JWT メールの一致を必須とする（fail-closed）。
- SSO_MODE=stub は `EDGE_AUTH_BOUNDARY=cloudflare-access` の明示宣言時のみ許可する。

## 結果

- 本番の未認証アクセスは Access チャレンジへ 302 で遮断される。
- 正式な Entra ID SSO 投入（#23/#50）までの暫定境界として、監査可能な形で運用できる。
