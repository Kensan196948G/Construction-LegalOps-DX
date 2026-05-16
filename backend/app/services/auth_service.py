"""Loop 5 wiring stub for :mod:`auth_service`.

Replace with concrete implementation when the corresponding feature
lands. See :mod:`app.services._stub` for the 501 contract.
"""

from __future__ import annotations

from app.services._stub import make_stub

_stub = make_stub("auth_service")


def __getattr__(item: str):
    return getattr(_stub, item)
