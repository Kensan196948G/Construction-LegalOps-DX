# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

### Added (Loop 1: プロジェクト基盤構築)

- リポジトリ初期スキャフォールドを追加。
- `README.md` を作成（プロジェクト概要・技術スタック・起動手順・AI 免責・ライセンス）。
- `LICENSE` (Apache License 2.0) を追加。著作権者: Construction-LegalOps-DX Contributors / 2026。
- `.gitignore` を整備（Python / Node / IDE / OS / env / SSL / DB / ログ）。
- `.env.example` を追加（DB / JWT / Entra ID / Claude API / SharePoint / desknet's NEO / Redis / CORS など）。
- `.editorconfig` を追加（UTF-8 / LF / フロント 2 スペース / Python 4 スペース）。
- `CONTRIBUTING.md` を追加（ブランチ命名 / Conventional Commits / PR テンプレ / AI レビュー人間確認義務）。
- `CHANGELOG.md` (Keep a Changelog 形式) を追加。
- GitHub Actions ワークフロー `.github/workflows/ci.yml` を追加（backend / frontend / security / docker build）。
- `infra/docker/docker-compose.yml` のサービス枠を追加（postgres / backend / frontend / nginx）。

### Notes

- 実装本体（FastAPI ルーター・Next.js ページ・認証フロー）は Loop 2 以降で追加予定。
- 本リリース時点で AI レビュー（Codex / CodeRabbit）連携は運用ドキュメントで定義済み、自動化は Loop 2 以降。

[Unreleased]: https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX/releases/tag/v0.1.0
