# Construction-LegalOps-DX — Backend

FastAPI backend for the Construction-LegalOps-DX platform (建設業法務・契約・コンプライアンス DX 基盤).

- Language: Python 3.12
- Framework: FastAPI + SQLAlchemy 2.x + Alembic
- Database: PostgreSQL 16 (asyncpg) / SQLite for local unit tests
- AI: Anthropic Claude API (drafts only — final legal judgment is always human)

For the full project documentation (architecture, security model, API coverage, release status), see the repository root [`README.md`](../README.md).

## Quick commands

```bash
# install (dev)
pip install -e ".[dev]"

# quality gates
ruff check .
mypy app
pytest
```
