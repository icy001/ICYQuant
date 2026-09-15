"""Commit 015 §5/§6/§12 — account sync configuration.

Same discipline as Commit 014's ``BrokerMarketDataConfig``: everything is
environment-driven and secrets are read here and nowhere else, so nothing
about *which* broker is wired in leaks into business logic and no
credential is ever hard-coded::

    ACCOUNT_ENABLED                 master switch                   (true)
    ACCOUNT_PROVIDER                provider name, e.g. "simulated"
    ACCOUNT_ENDPOINT                vendor account/position gateway
    ACCOUNT_ID                      default account id (NOT a secret)
    ACCOUNT_TOKEN                   API token  (SECRET, env only)
    ACCOUNT_PASSWORD                password   (SECRET, env only)
    ACCOUNT_TIMEOUT_SECONDS         request timeout                 (5.0)
    ACCOUNT_SYNC_INTERVAL_SECONDS   §6 snapshot cadence             (10.0)
    ACCOUNT_MAX_SYNC_AGE_SECONDS    §12 SYNCED → STALE threshold    (30.0)
    ACCOUNT_VALUATION               §18 value positions from mkt    (true)
    ACCOUNT_VOLUME_IN_LOTS          broker quantity is in 手        (false)
    ACCOUNT_STRICT_SYMBOLS          reject unknown symbols (§21)    (true)

:meth:`AccountSyncConfig.from_broker_config` lets the account adapter
**reuse Commit 014's** ``BrokerMarketDataConfig`` for the connection
knobs (provider / endpoint / account / token / timeout), which is the
"reuse the broker connection system, don't put the Account API inside
``BrokerMarketDataAdapter``" rule of §5.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

#: Provider used when none is configured — the dev / test provider.
DEFAULT_ACCOUNT_PROVIDER = "simulated"

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


@dataclass(frozen=True)
class AccountSyncConfig:
    """Resolved account / position sync settings (§5 / §6 / §12)."""

    enabled: bool = True
    provider: str = DEFAULT_ACCOUNT_PROVIDER
    endpoint: Optional[str] = None
    account_id: Optional[str] = None
    token: Optional[str] = None
    password: Optional[str] = None

    timeout_seconds: float = 5.0
    sync_interval_seconds: float = 10.0
    max_sync_age_seconds: float = 30.0

    valuation_enabled: bool = True
    volume_in_lots: bool = False
    strict_symbols: bool = True

    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AccountSyncConfig":
        """Build from ``ACCOUNT_*`` environment variables."""
        return cls(
            enabled=_env_bool("ACCOUNT_ENABLED", True),
            provider=(
                _env_str("ACCOUNT_PROVIDER", DEFAULT_ACCOUNT_PROVIDER)
                or DEFAULT_ACCOUNT_PROVIDER
            ),
            endpoint=_env_str("ACCOUNT_ENDPOINT"),
            account_id=_env_str("ACCOUNT_ID"),
            token=_env_str("ACCOUNT_TOKEN"),
            password=_env_str("ACCOUNT_PASSWORD"),
            timeout_seconds=max(
                0.0, _env_float("ACCOUNT_TIMEOUT_SECONDS", 5.0)
            ),
            sync_interval_seconds=max(
                0.0, _env_float("ACCOUNT_SYNC_INTERVAL_SECONDS", 10.0)
            ),
            max_sync_age_seconds=max(
                0.0, _env_float("ACCOUNT_MAX_SYNC_AGE_SECONDS", 30.0)
            ),
            valuation_enabled=_env_bool("ACCOUNT_VALUATION", True),
            volume_in_lots=_env_bool("ACCOUNT_VOLUME_IN_LOTS", False),
            strict_symbols=_env_bool("ACCOUNT_STRICT_SYMBOLS", True),
        )

    @classmethod
    def from_broker_config(
        cls, broker_config: object, **overrides: object
    ) -> "AccountSyncConfig":
        """Derive the account config from Commit 014's broker config (§5).

        The connection knobs (provider / endpoint / account / token /
        password / timeout) are shared; sync cadence stays account-local.
        """
        base = cls.from_env()
        payload: dict = {
            "enabled": base.enabled,
            "provider": getattr(broker_config, "provider", base.provider),
            "endpoint": getattr(broker_config, "endpoint", base.endpoint),
            "account_id": getattr(broker_config, "account", base.account_id),
            "token": getattr(broker_config, "token", base.token),
            "password": getattr(broker_config, "password", base.password),
            "timeout_seconds": getattr(
                broker_config, "timeout_seconds", base.timeout_seconds
            ),
            "sync_interval_seconds": base.sync_interval_seconds,
            "max_sync_age_seconds": base.max_sync_age_seconds,
            "valuation_enabled": base.valuation_enabled,
            "volume_in_lots": getattr(
                broker_config, "volume_in_lots", base.volume_in_lots
            ),
            "strict_symbols": base.strict_symbols,
        }
        payload.update(overrides)
        return cls(**payload)

    # ── derived ────────────────────────────────────────────────────────

    def secret_keys(self) -> tuple[str, ...]:
        return _SECRET_KEYS

    def has_credentials(self) -> bool:
        return bool(self.token or self.password)

    # ── serialisation (secrets redacted) ────────────────────────────────

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "account_id": self.account_id,
            "timeout_seconds": self.timeout_seconds,
            "sync_interval_seconds": self.sync_interval_seconds,
            "max_sync_age_seconds": self.max_sync_age_seconds,
            "valuation_enabled": self.valuation_enabled,
            "volume_in_lots": self.volume_in_lots,
            "strict_symbols": self.strict_symbols,
            "has_credentials": self.has_credentials(),
            "extra": dict(self.extra),
        }

    def describe(self) -> str:
        return (
            f"provider={self.provider} endpoint={self.endpoint or '-'} "
            f"interval={self.sync_interval_seconds}s "
            f"max_age={self.max_sync_age_seconds}s "
            f"valuation={'on' if self.valuation_enabled else 'off'} "
            f"credentials={'yes' if self.has_credentials() else 'no'}"
        )


__all__ = ["AccountSyncConfig", "DEFAULT_ACCOUNT_PROVIDER"]
