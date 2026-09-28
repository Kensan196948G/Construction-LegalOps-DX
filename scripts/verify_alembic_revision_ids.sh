#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — alembic migration chain preflight
#
# Checks that every migration is *storable* and that the chain is intact:
#
#   1. revision id length <= 32
#      `alembic_version.version_num` is `varchar(32)`. A longer id is accepted by
#      the DDL steps and then fails at the final UPDATE with
#      `StringDataRightTruncationError`, rolling the whole (transactional) DDL
#      back — i.e. the migration silently does nothing and reports a confusing
#      error. Measured 2026-09-28 with a 36-character id
#      (`027_evidence_hold_release_deleted_at`).
#   2. every `down_revision` resolves to a known revision (or None)
#   3. exactly one head (no accidental branching)
#
# Run before adding or merging a migration.
#
# Usage: scripts/verify_alembic_revision_ids.sh [versions-dir]
# Exit:  0 ok / 1 violation / 2 no migrations found (fail closed)
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_DIR="${1:-${REPO_ROOT}/backend/alembic/versions}"
MAX_LEN=32

[ -d "$VERSIONS_DIR" ] || {
  echo "❌ versions directory not found: $VERSIONS_DIR"
  exit 2
}

python3 - "$VERSIONS_DIR" "$MAX_LEN" <<'PY'
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

versions_dir = Path(sys.argv[1])
max_len = int(sys.argv[2])

files = sorted(p for p in versions_dir.glob("*.py") if p.name != "__init__.py")
if not files:
    print(f"❌ no migration files found in {versions_dir} (fail closed)")
    sys.exit(2)

entries: dict[str, Path] = {}
problems: list[str] = []


def literal(path: Path, name: str):
    """Return the value of a module-level `name: str = "..."` assignment."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                try:
                    return ast.literal_eval(node.value)
                except Exception:
                    return None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except Exception:
                        return None
    return None


down_refs: dict[str, object] = {}

for path in files:
    revision = literal(path, "revision")
    if not isinstance(revision, str) or not revision:
        # Fall back to a regex so unusual-but-valid files are still length-checked.
        m = re.search(r'^revision\s*(?::\s*str\s*)?=\s*["\']([^"\']+)["\']', path.read_text(encoding="utf-8"), re.M)
        revision = m.group(1) if m else None
    if not isinstance(revision, str) or not revision:
        problems.append(f"{path.name}: could not determine `revision`")
        continue
    if len(revision) > max_len:
        problems.append(
            f"{path.name}: revision id '{revision}' is {len(revision)} chars "
            f"(limit {max_len} — alembic_version.version_num is varchar({max_len}))"
        )
    if revision in entries:
        problems.append(f"{path.name}: duplicate revision id '{revision}' (also in {entries[revision].name})")
    entries[revision] = path
    down_refs[revision] = literal(path, "down_revision")

known = set(entries)
for revision, down in down_refs.items():
    refs = down if isinstance(down, (list, tuple)) else ([] if down is None else [down])
    for ref in refs:
        if ref is not None and ref not in known:
            problems.append(f"{entries[revision].name}: down_revision '{ref}' does not exist")

# Exactly one head: a revision that no other revision points down from.
referenced = set()
for down in down_refs.values():
    refs = down if isinstance(down, (list, tuple)) else ([] if down is None else [down])
    referenced.update(r for r in refs if r is not None)
heads = sorted(known - referenced)
if len(heads) != 1:
    problems.append(f"expected exactly 1 head, found {len(heads)}: {heads}")

if problems:
    for p in problems:
        print(f"❌ {p}")
    print(f"\n❌ alembic chain preflight failed ({len(problems)} problem(s))")
    sys.exit(1)

print(f"✅ alembic chain preflight passed ({len(entries)} revisions, head={heads[0]}, "
      f"max id length={max(len(r) for r in entries)}/{max_len})")
PY
