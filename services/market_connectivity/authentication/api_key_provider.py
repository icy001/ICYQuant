"""
API Key Provider — Manages exchange API keys with secure generation,
validation, and environment-based routing.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    key_id: str
    exchange_id: str
    api_key: str
    api_secret: str
    passphrase: str = ""
    permissions: list[str] = field(default_factory=list)
    environment: str = "production"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    rate_limit: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class APIKeyProvider:
    """
    Provides and manages exchange API keys.

    Supports secure key generation, HMAC signing, environment-based
    routing (production/test/sandbox), and key rotation.

    Usage::

        provider = APIKeyProvider()
        await provider.initialize()
        await provider.store(APIKey("binance", "binance", api_key="...", api_secret="..."))
        key = await provider.get("binance", environment="production")
    """

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, APIKey]] = {}

    async def initialize(self) -> None:
        """Initialize the API key provider."""
        logger.info("APIKeyProvider initialized.")

    # ---- Key Management ----

    async def store(self, key: APIKey) -> None:
        """Store an API key."""
        if key.exchange_id not in self._keys:
            self._keys[key.exchange_id] = {}
        self._keys[key.exchange_id][key.key_id] = key
        logger.info("API key stored: %s for %s", key.key_id, key.exchange_id)

    async def get(
        self, exchange_id: str, environment: str = "production"
    ) -> Optional[APIKey]:
        """Get an API key for an exchange and environment."""
        exchange_keys = self._keys.get(exchange_id, {})
        for key in exchange_keys.values():
            if key.environment == environment and not key.is_expired:
                return key
        return None

    async def get_by_id(self, key_id: str) -> Optional[APIKey]:
        """Get a specific key by ID."""
        for exchange_keys in self._keys.values():
            if key_id in exchange_keys:
                return exchange_keys[key_id]
        return None

    async def delete(self, key_id: str) -> bool:
        """Delete an API key."""
        for exchange_id, exchange_keys in list(self._keys.items()):
            if key_id in exchange_keys:
                del exchange_keys[key_id]
                if not exchange_keys:
                    del self._keys[exchange_id]
                return True
        return False

    async def list_keys(self, exchange_id: Optional[str] = None) -> list[APIKey]:
        """List all API keys, optionally filtered by exchange."""
        if exchange_id:
            return list(self._keys.get(exchange_id, {}).values())
        keys: list[APIKey] = []
        for exchange_keys in self._keys.values():
            keys.extend(exchange_keys.values())
        return keys

    # ---- Signing ----

    def sign_hmac(
        self, api_key: APIKey, payload: str, timestamp: Optional[int] = None
    ) -> dict[str, str]:
        """Generate HMAC-SHA256 signature headers."""
        ts = timestamp or int(time.time() * 1000)
        message = f"{ts}{payload}".encode()
        signature = hmac.new(
            api_key.api_secret.encode(), message, hashlib.sha256
        ).hexdigest()

        return {
            "X-API-KEY": api_key.api_key,
            "X-SIGNATURE": signature,
            "X-TIMESTAMP": str(ts),
        }

    def sign_message(
        self, api_key: APIKey, method: str, path: str, body: str = "",
        timestamp: Optional[int] = None,
    ) -> dict[str, str]:
        """Generate exchange-standard signature headers."""
        ts = timestamp or int(time.time() * 1000)
        message = f"{ts}{method}{path}{body}".encode()
        signature = hmac.new(
            api_key.api_secret.encode(), message, hashlib.sha256
        ).hexdigest()

        headers = {
            "X-API-KEY": api_key.api_key,
            "X-SIGNATURE": signature,
            "X-TIMESTAMP": str(ts),
        }
        if api_key.passphrase:
            headers["X-PASSPHRASE"] = api_key.passphrase
        return headers

    # ---- Key Generation ----

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a secure random API key."""
        return secrets.token_hex(length)

    @staticmethod
    def generate_api_secret(length: int = 64) -> str:
        """Generate a secure random API secret."""
        return secrets.token_hex(length)

    async def get_summary(self) -> dict[str, Any]:
        """Get API key summary."""
        total = sum(len(keys) for keys in self._keys.values())
        return {
            "total_keys": total,
            "exchanges": list(self._keys.keys()),
            "keys_per_exchange": {
                eid: len(keys) for eid, keys in self._keys.items()
            },
        }
