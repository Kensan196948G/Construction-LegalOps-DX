"""一次情報限定 RAG — 法令コーパス（backend/data/legal_sources）の読み込みと検索.

検索対象は ``backend/data/legal_sources/*.md`` に置かれた、公的機関の
一次情報 URL を明記した社内整備コーパスのみ。外部 Web を直接検索しない。
パッケージインストール時に data ディレクトリが存在しない場合は空コーパスに
フォールバックし、捏造回答は行わない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "legal_sources"

_URL_RE = re.compile(r"https?://[^\s)\]]+")


@dataclass(slots=True)
class CorpusDoc:
    """A single Markdown corpus document with its primary source URL."""

    source_id: str
    title: str
    body: str
    source_url: str | None = None
    law_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_url": self.source_url,
            "law_tags": self.law_tags,
            "body": self.body,
        }


def _parse_markdown(path: Path) -> CorpusDoc:
    text = path.read_text(encoding="utf-8")
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = path.stem
    urls = [u.rstrip(").,;") for u in _URL_RE.findall(text)]
    tags: list[str] = []
    for tag in ("取適法", "建設業法", "個人情報保護法", "電子帳簿保存法"):
        if tag in text:
            tags.append(tag)
    return CorpusDoc(
        source_id=path.stem,
        title=title,
        body=text,
        source_url=urls[0] if urls else None,
        law_tags=tags,
    )


def load_corpus() -> list[CorpusDoc]:
    """Load all Markdown corpus documents under ``data/legal_sources``."""

    if not _CORPUS_DIR.is_dir():
        return []
    docs: list[CorpusDoc] = []
    for path in sorted(_CORPUS_DIR.glob("*.md")):
        try:
            docs.append(_parse_markdown(path))
        except OSError:  # pragma: no cover - unreadable corpus file
            continue
    return docs


def corpus_search(query: str, *, limit: int = 8) -> list[CorpusDoc]:
    """Keyword-overlap search over the local primary-source corpus."""

    terms = [
        t.strip()
        for t in query.replace("、", " ").replace("，", " ").replace(" ", " ").split()
        if t.strip()
    ]
    if not terms:
        return []
    scored: list[tuple[float, CorpusDoc]] = []
    for doc in load_corpus():
        haystack = f"{doc.title}\n{doc.body}".lower()
        hits = sum(1 for t in terms if t.lower() in haystack)
        if hits <= 0:
            continue
        # Title matches weigh more than body matches.
        title_hits = sum(1 for t in terms if t.lower() in doc.title.lower())
        score = (hits / len(terms)) + (0.2 * title_hits)
        scored.append((score, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def corpus_stats() -> dict[str, Any]:
    """Return corpus integrity stats (used by tests and diagnostics)."""

    docs = load_corpus()
    return {
        "document_count": len(docs),
        "documents": [
            {"source_id": d.source_id, "has_source_url": bool(d.source_url)}
            for d in docs
        ],
        "all_have_source_url": all(bool(d.source_url) for d in docs),
    }


__all__ = ["CorpusDoc", "corpus_search", "corpus_stats", "load_corpus"]
