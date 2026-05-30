"""Template and clause-library service.

Provides an in-memory implementation of templates and clause-library entries
for construction-industry contracts. A dedicated DB table is planned for a
future loop; until then, data is stored as module-level Python dataclass
instances so the API surface is fully functional without a migration.

All ``create_*`` and ``update_*`` mutation methods raise ``NotImplementedError``
because writes require persistent storage that is not yet in place.
The API routers convert ``NotImplementedError`` to HTTP 501.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clause import ClauseLibrary
from app.models.user import User
from app.schemas.template import (
    ClauseLibraryCreate,
    ClauseLibraryOut,
    ClauseLibraryUpdate,
    TemplateCreate,
)

# ---------------------------------------------------------------------------
# Baseline timestamp used for all seeded records.
# ---------------------------------------------------------------------------
_STUB_TS = datetime(2026, 1, 1, tzinfo=UTC)  # fixed timestamp for seeded stub records


# ---------------------------------------------------------------------------
# Helpers to build SimpleNamespace rows that satisfy ORMModel.model_validate
# (from_attributes=True, so dot-attribute access is sufficient).
# ---------------------------------------------------------------------------


def _tmpl(
    id: int,
    code: str,
    name: str,
    contract_type: str,
    description: str | None,
    body: str,
    is_active: bool = True,
    version: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        code=code,
        name=name,
        contract_type=contract_type,
        description=description,
        body=body,
        is_active=is_active,
        version=version,
        created_at=_STUB_TS,
        updated_at=_STUB_TS,
    )


def _clause(
    id: int,
    code: str,
    title: str,
    category: str,
    recommendation: str,
    text: str,
    tags: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        code=code,
        title=title,
        category=category,
        recommendation=recommendation,
        text=text,
        tags=tags or [],
        created_at=_STUB_TS,
        updated_at=_STUB_TS,
    )


# ---------------------------------------------------------------------------
# Seed data — construction-industry templates
# ---------------------------------------------------------------------------

_TEMPLATES: list[SimpleNamespace] = [
    _tmpl(
        id=1,
        code="TMPL-UKEOI-001",
        name="工事請負契約書（標準）",
        contract_type="請負",
        description="建設業法第18条に基づく工事請負契約の標準ひな形。",
        body=(
            "工事請負契約書\n\n"
            "発注者（以下「甲」）と受注者（以下「乙」）は、以下のとおり工事請負契約を締結する。\n\n"
            "第1条（目的）\n甲は乙に対し、別紙仕様書に記載の工事（以下「本工事」）を請け負わせ、"
            "乙はこれを受注する。\n\n"
            "第2条（工期）\n本工事の工期は別紙に定めるとおりとする。\n\n"
            "第3条（請負代金）\n本工事の請負代金は別紙に定めるとおりとする。"
        ),
    ),
    _tmpl(
        id=2,
        code="TMPL-SHITAUKE-001",
        name="下請契約書（専門工事）",
        contract_type="請負",
        description="専門工事業者との下請契約ひな形。建設業法第24条の2以下の規定を考慮済み。",
        body=(
            "下請契約書\n\n"
            "元請負人（以下「甲」）と下請負人（以下「乙」）は、下記のとおり下請契約を締結する。\n\n"
            "第1条（下請工事の内容）\n甲が請け負った工事のうち、別紙記載の工事を乙に下請負させる。\n\n"
            "第2条（下請代金）\n下請代金額は別紙に定めるとおりとし、"
            "甲は乙に対し完成検査合格後30日以内に支払う。\n\n"
            "第3条（工期）\n本工事の工期は別紙に定めるとおりとする。"
        ),
    ),
    _tmpl(
        id=3,
        code="TMPL-ITAKU-001",
        name="業務委託契約書（設計業務）",
        contract_type="委託",
        description="建築設計・監理業務を委託するためのひな形。",
        body=(
            "業務委託契約書\n\n"
            "委託者（以下「甲」）と受託者（以下「乙」）は、以下のとおり業務委託契約を締結する。\n\n"
            "第1条（委託業務）\n甲は乙に対し、別紙仕様書記載の業務（以下「本業務」）を委託する。\n\n"
            "第2条（委託料）\n委託料は別紙に定めるとおりとし、業務完了後30日以内に支払う。\n\n"
            "第3条（再委託の禁止）\n乙は甲の書面による事前承諾なく本業務を第三者に再委託してはならない。"
        ),
    ),
    _tmpl(
        id=4,
        code="TMPL-NDA-001",
        name="秘密保持契約書",
        contract_type="秘密保持",
        description="入札前・設計前の機密情報開示に際して締結する NDA ひな形。",
        body=(
            "秘密保持契約書\n\n"
            "開示者（以下「甲」）と受領者（以下「乙」）は、以下のとおり秘密保持契約を締結する。\n\n"
            "第1条（定義）\n「秘密情報」とは、甲が乙に開示する技術上・営業上の情報であって、"
            "開示の際に秘密である旨を明示したものをいう。\n\n"
            "第2条（秘密保持義務）\n乙は秘密情報を厳重に管理し、甲の事前承諾なく第三者に開示してはならない。\n\n"
            "第3条（有効期間）\n本契約の有効期間は締結日から3年間とする。"
        ),
    ),
    _tmpl(
        id=5,
        code="TMPL-JV-001",
        name="建設工事共同企業体（JV）協定書",
        contract_type="JV",
        description="特定建設工事共同企業体（特定 JV）の協定書ひな形。",
        body=(
            "建設工事共同企業体協定書\n\n"
            "本協定書は、下記工事を共同で請け負うことを目的に組成する"
            "建設工事共同企業体（以下「本JV」）に関して、構成員間の権利義務を定める。\n\n"
            "第1条（目的）\n本JVは、別紙記載の工事を共同で請け負い遂行することを目的とする。\n\n"
            "第2条（出資比率・構成員）\n各構成員の出資比率は別紙に定めるとおりとする。\n\n"
            "第3条（代表者）\n本JVを代表するスポンサーを別紙に定める。"
        ),
        is_active=True,
        version=1,
    ),
]

# ---------------------------------------------------------------------------
# Seed data — clause library (linked to template IDs 1–5 conceptually but
# stored flat; filtering by template_id is not currently supported).
# ---------------------------------------------------------------------------

_CLAUSES: list[SimpleNamespace] = [
    # ---- 工事請負 / 下請 共通条項 ----
    _clause(
        id=1,
        code="CL-DEFECT-001",
        title="瑕疵担保責任条項",
        category="品質保証",
        recommendation="recommended",
        text=(
            "乙は本工事完成引渡し後、建設業法第40条の3に定める期間内に発見された"
            "瑕疵について、無償で補修する責任を負う。"
        ),
        tags=["瑕疵担保", "品質", "請負"],
    ),
    _clause(
        id=2,
        code="CL-DELAY-001",
        title="工期遅延違約金条項",
        category="違約金",
        recommendation="recommended",
        text=(
            "乙の責めに帰すべき事由により工期が遅延した場合、乙は遅延1日につき"
            "請負代金額の0.1%に相当する違約金を甲に支払う。"
        ),
        tags=["遅延", "違約金", "工期"],
    ),
    _clause(
        id=3,
        code="CL-FORCE-001",
        title="不可抗力条項",
        category="免責",
        recommendation="recommended",
        text=(
            "天災地変、戦争、感染症の流行その他当事者の責めに帰すことができない"
            "事由による履行不能については、各当事者はその責を負わない。"
        ),
        tags=["不可抗力", "免責", "リスク"],
    ),
    _clause(
        id=4,
        code="CL-PAYMENT-001",
        title="出来高払い条項",
        category="代金支払",
        recommendation="recommended",
        text=(
            "甲は、工事の出来高に応じて月次で請負代金を支払う。"
            "請求書受領後30日以内に支払うものとし、遅延した場合は年3%の遅延損害金が発生する。"
        ),
        tags=["出来高払い", "支払条件", "請負代金"],
    ),
    _clause(
        id=5,
        code="CL-SUBCON-PROHIBIT-001",
        title="一括下請負禁止条項",
        category="下請管理",
        recommendation="recommended",
        text=("乙は、建設業法第22条に基づき、本工事を一括して第三者に下請負させてはならない。"),
        tags=["一括下請負禁止", "建設業法", "下請"],
    ),
    _clause(
        id=6,
        code="CL-DESIGN-IP-001",
        title="設計成果物の著作権帰属条項",
        category="知的財産",
        recommendation="recommended",
        text=(
            "本業務により乙が作成した設計図書等の著作権は乙に帰属するが、"
            "甲は本工事の施工および維持管理に必要な範囲で無償で利用できる。"
        ),
        tags=["著作権", "設計", "知的財産"],
    ),
    _clause(
        id=7,
        code="CL-CONF-001",
        title="秘密情報の例外条項",
        category="秘密保持",
        recommendation="recommended",
        text=(
            "以下の情報は秘密情報に含まれない：(1) 開示時点で既に公知であった情報；"
            "(2) 開示後に乙の責めによらず公知となった情報；"
            "(3) 乙が独自に開発した情報。"
        ),
        tags=["秘密保持", "例外", "NDA"],
    ),
    _clause(
        id=8,
        code="CL-DISPUTE-001",
        title="紛争解決・管轄条項",
        category="紛争解決",
        recommendation="recommended",
        text=(
            "本契約に関する紛争は、まず両当事者が誠実に協議して解決するものとし、"
            "協議が整わない場合は東京地方裁判所を第一審の専属的合意管轄裁判所とする。"
        ),
        tags=["紛争解決", "管轄", "裁判所"],
    ),
    _clause(
        id=9,
        code="CL-CANCEL-PENALTY-001",
        title="契約解除違約金（注意事項）",
        category="違約金",
        recommendation="caution",
        text=(
            "甲の都合による契約解除の場合、甲は未施工分の請負代金の10%相当額を"
            "違約金として乙に支払う。この条項は消費者契約法の適用がある場合には無効となりうる。"
        ),
        tags=["違約金", "解除", "注意"],
    ),
    _clause(
        id=10,
        code="CL-EXEMPT-ALL-001",
        title="全責任免除条項（禁止）",
        category="免責",
        recommendation="prohibited",
        text=(
            "乙は本工事に関して発生したいかなる損害についても一切責任を負わない。"
            "（注: このような包括的免責条項は民法上無効となる場合があり使用禁止。）"
        ),
        tags=["免責", "禁止", "無効リスク"],
    ),
]

# Fast lookup by id.
_TEMPLATES_BY_ID: dict[int, SimpleNamespace] = {t.id: t for t in _TEMPLATES}
_CLAUSES_BY_ID: dict[int, SimpleNamespace] = {c.id: c for c in _CLAUSES}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_templates(
    session: AsyncSession,
    *,
    contract_type: str | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Any], int]:
    """Return a paginated list of templates, optionally filtered."""
    results = list(_TEMPLATES)

    if contract_type:
        results = [t for t in results if t.contract_type == contract_type]

    if is_active is not None:
        results = [t for t in results if t.is_active == is_active]

    if q:
        q_lower = q.lower()
        results = [
            t
            for t in results
            if q_lower in t.name.lower() or q_lower in (t.description or "").lower()
        ]

    total = len(results)
    offset = (page - 1) * size
    return results[offset : offset + size], total


async def get_template(
    session: AsyncSession,
    *,
    template_id: int,
) -> SimpleNamespace | None:
    """Return a single template by ID, or ``None`` if not found."""
    return _TEMPLATES_BY_ID.get(template_id)


async def create_template(
    session: AsyncSession,
    *,
    data: TemplateCreate,
    creator: User,
) -> Any:
    """Create a template. Not yet implemented (no persistent store)."""
    raise NotImplementedError(
        "template_service.create_template: DB table for templates is planned for a future loop"
    )


def _clause_to_out(clause: ClauseLibrary) -> ClauseLibraryOut:
    """Map ORM ClauseLibrary to ClauseLibraryOut.

    ``ClauseLibrary.body`` is exposed as ``ClauseLibraryOut.text`` to
    satisfy the API schema contract.
    """
    return ClauseLibraryOut(
        id=clause.id,
        code=clause.code,
        title=clause.title,
        category=clause.category,
        recommendation=clause.recommendation,
        text=clause.body,
        tags=list(clause.tags or []),
        created_at=clause.created_at,
        updated_at=clause.updated_at,
    )


async def list_clauses(
    session: AsyncSession,
    *,
    category: str | None = None,
    recommendation: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    template_id: int | None = None,  # reserved for future use
    page: int = 1,
    size: int = 20,
) -> tuple[list[ClauseLibraryOut], int]:
    """Return a paginated list of ClauseLibrary entries from the database."""
    stmt = select(ClauseLibrary).where(ClauseLibrary.deleted_at.is_(None))

    if category:
        stmt = stmt.where(ClauseLibrary.category == category)
    if recommendation:
        stmt = stmt.where(ClauseLibrary.recommendation == recommendation)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                ClauseLibrary.title.ilike(pattern),
                ClauseLibrary.body.ilike(pattern),
            )
        )

    count_q = await session.execute(select(func.count()).select_from(stmt.subquery()))
    total: int = count_q.scalar() or 0

    data_q = await session.execute(
        stmt.order_by(ClauseLibrary.id).offset((page - 1) * size).limit(size)
    )
    rows = data_q.scalars().all()

    # tag filter is applied in Python (ARRAY contains varies across dialects)
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]
        total = len(rows)

    return [_clause_to_out(r) for r in rows], total


async def create_clause(
    session: AsyncSession,
    *,
    data: ClauseLibraryCreate,
    creator: User,
) -> ClauseLibraryOut:
    """Create and persist a clause-library entry."""
    clause = ClauseLibrary(
        code=data.code,
        title=data.title,
        category=data.category,
        body=data.text,
        recommendation=data.recommendation,
        tags=data.tags,
    )
    session.add(clause)
    await session.flush()
    await session.refresh(clause)
    return _clause_to_out(clause)


async def update_clause(
    session: AsyncSession,
    *,
    clause_id: int,
    data: ClauseLibraryUpdate,
    editor: User,
) -> ClauseLibraryOut:
    """Apply a partial update to a ClauseLibrary entry.

    Raises
    ------
    LookupError
        When ``clause_id`` does not exist or is soft-deleted.
    """
    result = await session.execute(
        select(ClauseLibrary).where(
            ClauseLibrary.id == clause_id,
            ClauseLibrary.deleted_at.is_(None),
        )
    )
    clause = result.scalar_one_or_none()
    if clause is None:
        raise LookupError(f"clause {clause_id} not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        # ClauseLibraryUpdate.text maps to ClauseLibrary.body
        db_field = "body" if field == "text" else field
        setattr(clause, db_field, value)

    await session.flush()
    await session.refresh(clause)
    return _clause_to_out(clause)
