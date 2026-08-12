# ADR（Architecture Decision Records）

本ディレクトリは、Construction-LegalOps-DX の主要な設計判断を記録するための ADR 台帳です。

| ADR | タイトル | 状態 | 決定日 |
| --- | --- | --- | --- |
| [0001](0001-web-stack.md) | FastAPI + Next.js + PostgreSQL を採用する | Accepted | 2026-05-16 |
| [0002](0002-ai-human-approval.md) | AI 出力は常に人間レビューを必須とする | Accepted | 2026-06-01 |
| [0003](0003-audit-hash-chain.md) | 監査ログを SHA-256 ハッシュチェーンで保護する | Accepted | 2026-06-10 |
| [0004](0004-rls-acl.md) | PostgreSQL RLS + 案件単位 ACL でデータ境界を実装する | Accepted | 2026-07-20 |
| [0005](0005-cloudflare-access-boundary.md) | 本番認証境界を Cloudflare Access とする | Accepted | 2026-07-20 |
| [0006](0006-app-rate-limit.md) | アプリ層レート制限を ASGI ミドルウェアで実装する | Accepted | 2026-08-12 |

ADR の追加・変更時は、この README の一覧も更新してください。
