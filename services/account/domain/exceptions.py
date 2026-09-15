"""Domain-level account / position errors (Commit 015).

These are raised by the *pure* domain objects and carry no transport
knowledge.  The sync pipeline defines its own richer errors in
:mod:`services.account.sync.exceptions` on top of :class:`AccountError`.
"""
from __future__ import annotations


class AccountError(Exception):
    """Base class for every account / position failure."""

    code = "ACCOUNT_ERROR"

    def __init__(self, detail: str = "", **context: object) -> None:
        super().__init__(detail or self.code)
        self.detail = detail or self.code
        self.context = dict(context)

    def as_dict(self) -> dict:
        payload: dict = {"error": self.code, "detail": self.detail}
        payload.update(self.context)
        return payload


class AccountValidationError(AccountError):
    """A balance / snapshot failed a basic consistency rule."""

    code = "ACCOUNT_VALIDATION_ERROR"


class InvalidPositionError(AccountError):
    """A position violates ``quantity == available + frozen`` (§3)."""

    code = "POSITION_INVALID"


__all__ = [
    "AccountError",
    "AccountValidationError",
    "InvalidPositionError",
]
