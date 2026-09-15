"""Account sync pipeline errors (Commit 015).

Extend the domain :class:`~services.account.domain.exceptions.AccountError`
so the API can render one envelope, and carry an HTTP ``status_code`` so
``apps/api`` maps them without a second lookup table.
"""
from __future__ import annotations

from typing import Any

from services.account.domain.exceptions import AccountError


class AccountSyncError(AccountError):
    """Base class for account / position sync failures."""

    code = "ACCOUNT_SYNC_ERROR"
    status_code = 500


class AccountNotFoundError(AccountSyncError):
    """Unknown account id → 404."""

    code = "ACCOUNT_NOT_FOUND"
    status_code = 404


class AccountSnapshotNotFoundError(AccountSyncError):
    """No snapshot retained for the account → 404."""

    code = "ACCOUNT_SNAPSHOT_NOT_FOUND"
    status_code = 404


class BrokerAccountError(AccountSyncError):
    """A vendor-side account/position request failed."""

    code = "BROKER_ACCOUNT_ERROR"
    status_code = 502


class BrokerAccountConnectionError(BrokerAccountError):
    """The broker account channel is down / could not be opened."""

    code = "BROKER_ACCOUNT_CONNECTION_ERROR"
    status_code = 503


class BrokerAccountNotConnectedError(BrokerAccountError):
    """``get_account`` / ``get_positions`` called before ``connect()``."""

    code = "BROKER_ACCOUNT_NOT_CONNECTED"
    status_code = 409


class AccountProviderUnknownError(BrokerAccountError):
    """The configured provider has no registered factory → 400."""

    code = "ACCOUNT_PROVIDER_UNKNOWN"
    status_code = 400


class AccountNormalizationError(AccountSyncError):
    """A broker payload cannot be mapped to the standard model."""

    code = "ACCOUNT_NORMALIZATION_ERROR"
    status_code = 422


class UnknownAccountSymbolError(AccountNormalizationError):
    """A position references a symbol outside the Instrument Master (§21)."""

    code = "ACCOUNT_UNKNOWN_SYMBOL"
    status_code = 422


class InvalidAccountTransition(AccountSyncError):
    """An illegal account-status transition was attempted (§12)."""

    code = "ACCOUNT_INVALID_TRANSITION"
    status_code = 409


class AccountStateError(AccountSyncError):
    """The account is in a state that forbids the requested operation."""

    code = "ACCOUNT_STATE_ERROR"
    status_code = 409


def as_error(payload: Any) -> AccountSyncError:  # pragma: no cover - helper
    """Coerce an arbitrary error into an :class:`AccountSyncError`."""
    if isinstance(payload, AccountSyncError):
        return payload
    return AccountSyncError(str(payload))


__all__ = [
    "AccountSyncError",
    "AccountNotFoundError",
    "AccountSnapshotNotFoundError",
    "BrokerAccountError",
    "BrokerAccountConnectionError",
    "BrokerAccountNotConnectedError",
    "AccountProviderUnknownError",
    "AccountNormalizationError",
    "UnknownAccountSymbolError",
    "InvalidAccountTransition",
    "AccountStateError",
    "as_error",
]
