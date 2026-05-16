"""Loop 5 wiring stubs.

These stub modules satisfy router imports so :mod:`app.main` can be
loaded and routes can be enumerated even before the corresponding
business logic ships. Each unknown attribute resolves to an async
callable that raises ``HTTPException(501)`` so accidental calls fail
loudly instead of returning misleading 200s.

Loop 6 / future loops will replace individual modules with concrete
implementations; importers MUST keep using module-level functions so
the swap is a no-op at the call site.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def make_stub(service_name: str) -> Any:
    """Return a module-like object whose attributes are 501 coroutines."""

    class _Stub:
        __name__ = service_name
        ALLOWED_MIME_TYPES = {  # noqa: RUF012
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
        }

        def __getattr__(self, item: str) -> Any:  # pragma: no cover - trivial
            async def _not_implemented(*_a: Any, **_kw: Any) -> Any:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail=(
                        f"{service_name}.{item} is not implemented yet "
                        "(Loop 5 wiring stub)."
                    ),
                )

            _not_implemented.__name__ = item
            return _not_implemented

    return _Stub()
