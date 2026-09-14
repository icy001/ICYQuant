"""Broker market data configuration (Commit 014 §4).

The adapter must be operator-configurable and vendor-agnostic: nothing
about *which* broker is wired in may leak into business logic.  All
knobs are environment-driven, never hard-coded::

    MARKET_DATA_ENABLED                 master switch              (true)
    MARKET_DATA_PROVIDER                provider name, e.g. "simulated"
    MARKET_DATA_ENDPOINT                vendor endpoint / gateway URL
    MARKET_DATA_ACCOUNT                 account id (NOT a secret)
    MARKET_DATA_TOKEN                   API token  (SECRET, env only)
    MARKET_DATA_PASSWORD                password   (SECRET, env only)
    MARKET_DATA_TIMEOUT_SECONDS         poll / dial timeout         (5.0)
    MARKET_DATA_RECONNECT_SECONDS       §7 delay between attempts   (3.0)
    MARKET_DATA_MAX_RECONNECT_ATTEMPTS  §7 attempts, 0 = unlimited  (5)
    MARKET_DATA_RESUBSCRIBE             §7 resubscribe after drop   (true)
    MARKET_DATA_VOLUME_IN_LOTS          broker volume is in 手       (false)

Secret discipline (§4):

    environment variables
            ↓
    BrokerMarketDataConfig
            ↓
    Broker Adapter

``account`` / ``password`` / ``token`` are read from the environment and
never default to a literal.  :meth:`as_dict` and :meth:`describe` redact
them, so a config dump can be logged / served to the Dashboard without
leaking credentials.

Only the *shape* of this config is fixed by Commit 014; concrete field
names are adapted to the final vendor SDK in a later commit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

#: Provider used when none is configured.  ``simulated`` is the dev /
#: test provider (see ``adapters.broker``); production must set a real
#: provider via ``MARKET_DATA_PROVIDER``.
DEFAULT_PROVIDER = "simulated"

_SECRET_KEYS = ("token", "password")


def _env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "y")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class BrokerMarketDataConfig:
    """Resolved broker adapter settings (§4).

    Frozen so a running adapter's config cannot be mutated underneath
    it — a credential rotation means constructing a new adapter.
    """

    enabled: bool = True
    provider: str = DEFAULT_PROVIDER
    endpoint: Optional[str] = None
    account: Optional[str] = None
    token: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: float = 5.0
    reconnect_seconds: float = 3.0
    max_reconnect_attempts: int = 5
    resubscribe_on_reconnect: bool = True
    volume_in_lots: bool = False
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "BrokerMarketDataConfig":
        """Build from ``MARKET_DATA_*`` environment variables.

        Credentials are read here and nowhere else, so they never enter
        the source tree (§4).
        """
        return cls(
            enabled=_env_bool("MARKET_DATA_ENABLED", True),
            provider=(
                _env_str("MARKET_DATA_PROVIDER", DEFAULT_PROVIDER)
                or DEFAULT_PROVIDER
            ),
            endpoint=_env_str("MARKET_DATA_ENDPOINT"),
            account=_env_str("MARKET_DATA_ACCOUNT"),
            token=_env_str("MARKET_DATA_TOKEN"),
            password=_env_str("MARKET_DATA_PASSWORD"),
            timeout_seconds=max(
                0.0, _env_float("MARKET_DATA_TIMEOUT_SECONDS", 5.0)
            ),
            reconnect_seconds=max(
                0.0, _env_float("MARKET_DATA_RECONNECT_SECONDS", 3.0)
            ),
            max_reconnect_attempts=max(
                0, _env_int("MARKET_DATA_MAX_RECONNECT_ATTEMPTS", 5)
            ),
            resubscribe_on_reconnect=_env_bool(
                "MARKET_DATA_RESUBSCRIBE", True
            ),
            volume_in_lots=_env_bool("MARKET_DATA_VOLUME_IN_LOTS", False),
        )

    # ── derived ────────────────────────────────────────────────

    def secret_keys(self) -> tuple[str, ...]:
        """Names of fields that must never be logged or serialised."""
        return _SECRET_KEYS

    def has_credentials(self) -> bool:
        """Whether a usable credential was supplied (never the value)."""
        return bool(self.token or self.password)

    # ── serialisation (secrets redacted) ───────────────────────

    def as_dict(self) -> dict:
        """Full config view with secrets replaced by a presence flag."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "account": self.account,
            "timeout_seconds": self.timeout_seconds,
            "reconnect_seconds": self.reconnect_seconds,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "resubscribe_on_reconnect": self.resubscribe_on_reconnect,
            "volume_in_lots": self.volume_in_lots,
            "has_credentials": self.has_credentials(),
            "extra": dict(self.extra),
        }

    def describe(self) -> str:
        """Single-line, secret-free summary for logs."""
        endpoint = self.endpoint or "-"
        return (
            f"provider={self.provider} endpoint={endpoint} "
            f"timeout={self.timeout_seconds}s "
            f"reconnect={self.reconnect_seconds}s "
            f"max_attempts={self.max_reconnect_attempts} "
            f"credentials={'yes' if self.has_credentials() else 'no'}"
        )


__all__ = ["BrokerMarketDataConfig", "DEFAULT_PROVIDER"]
