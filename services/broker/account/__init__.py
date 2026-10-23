"""Commit 015 §5 — Broker Account Adapter.

    BrokerAccountAdapter          contract (connect / get_account /
                                  get_positions)
    AccountProvider               vendor SDK wrapper (raw mappings)
    ProviderBrokerAccountAdapter  provider-backed implementation
    AccountNormalizer             raw payload → AccountBalance / Position
    SimulatedAccountProvider      dev / test provider

Field-name vocabulary lives in :mod:`.models`, so a new broker is data
(a new alias table / provider), not a rewrite (§5).
"""
from __future__ import annotations

from .base import BrokerAccountAdapter
from .broker_account import (
    AccountProvider,
    ProviderBrokerAccountAdapter,
    ProviderFactory,
    SimulatedAccountProvider,
    build_account_provider,
    provider_names,
    register_provider,
    unregister_provider,
)
from .models import (
    ACCOUNT_FIELD_ALIASES,
    POSITION_FIELD_ALIASES,
    POSITION_REQUIRED_FIELDS,
    as_mapping,
    extra_fields,
    missing_fields,
    normalize_key,
    resolve_field,
    resolve_fields,
)
from .normalizer import AccountNormalizer, LOT_SIZE

__all__ = [
    "BrokerAccountAdapter",
    "AccountProvider",
    "ProviderFactory",
    "ProviderBrokerAccountAdapter",
    "SimulatedAccountProvider",
    "build_account_provider",
    "provider_names",
    "register_provider",
    "unregister_provider",
    "AccountNormalizer",
    "LOT_SIZE",
    "ACCOUNT_FIELD_ALIASES",
    "POSITION_FIELD_ALIASES",
    "POSITION_REQUIRED_FIELDS",
    "as_mapping",
    "extra_fields",
    "missing_fields",
    "normalize_key",
    "resolve_field",
    "resolve_fields",
]
