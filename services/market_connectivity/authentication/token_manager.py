"""
Token Manager — Manages JWT, OAuth, and session tokens for exchange
authentication with refresh, rotation, and expiry tracking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    JWT = "jwt"
    OAUTH_ACCESS = "oauth_access"
    OAUTH_REFRESH = "oauth_refresh"
    SESSION = "session"
    BEARER = "bearer"


@dataclass
class Token:
    token_id: str
    exchange_id: str
    token_type: TokenType
    access_token: str
    refresh_token: str = ""
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    scope: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def can_refresh(self) -> bool:
        if not self.refresh_token:
            return False
        if self.refresh_expires_at is None:
            return True
        return datetime.now(timezone.utc) < self.refresh_expires_at

    @property
    def ttl_seconds(self) -> float:
        if self.expires_at is None:
            return 0.0
        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)


class TokenManager:
    """
    Manages authentication tokens for exchange connectivity.

    Handles JWT, OAuth 2.0, and session tokens with automatic
    refresh, rotation, and expiry tracking.

    Usage::

        manager = TokenManager()
        await manager.initialize()
        await manager.store(Token("binance_web", "binance", TokenType.BEARER, access_token="..."))
        token = await manager.get("binance", TokenType.BEARER)
        token = await manager.refresh_if_needed("binance", TokenType.BEARER)
    """

    def __init__(self, auto_refresh: bool = True, refresh_before_expiry: float = 60.0) -> None:
        self.auto_refresh = auto_refresh
        self.refresh_before_expiry = refresh_before_expiry
        self._tokens: dict[str, dict[TokenType, Token]] = {}
        self._refresh_callbacks: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the token manager."""
        logger.info("TokenManager initialized.")

    def set_refresh_callback(self, exchange_id: str, callback: Any) -> None:
        """Register a callback for token refresh."""
        self._refresh_callbacks[exchange_id] = callback

    # ---- Token Management ----

    async def store(self, token: Token) -> None:
        """Store a token."""
        async with self._lock:
            if token.exchange_id not in self._tokens:
                self._tokens[token.exchange_id] = {}
            self._tokens[token.exchange_id][token.token_type] = token
        logger.info("Token stored: %s for %s (%s)", token.token_id, token.exchange_id, token.token_type.value)

    async def get(
        self, exchange_id: str, token_type: TokenType = TokenType.BEARER
    ) -> Optional[Token]:
        """Get a token for an exchange."""
        exchange_tokens = self._tokens.get(exchange_id, {})
        token = exchange_tokens.get(token_type)

        if token is None:
            return None

        if token.is_expired and token.can_refresh:
            if self.auto_refresh:
                logger.info("Auto-refreshing token for %s", exchange_id)
                return await self.refresh(exchange_id, token_type)

        return token if not token.is_expired else None

    async def delete(self, exchange_id: str, token_type: TokenType) -> bool:
        """Delete a token."""
        async with self._lock:
            exchange_tokens = self._tokens.get(exchange_id, {})
            return exchange_tokens.pop(token_type, None) is not None

    async def refresh(
        self, exchange_id: str, token_type: TokenType = TokenType.BEARER
    ) -> Optional[Token]:
        """Refresh a token using the refresh callback."""
        token = self._tokens.get(exchange_id, {}).get(token_type)
        if token is None:
            return None
        if not token.can_refresh:
            logger.warning("Token %s cannot be refreshed", token.token_id)
            return None

        callback = self._refresh_callbacks.get(exchange_id)
        if callback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    new_token: Token = await callback(token)
                else:
                    new_token = callback(token)
                await self.store(new_token)
                logger.info("Token refreshed: %s", new_token.token_id)
                return new_token
            except Exception:
                logger.exception("Token refresh failed for %s", exchange_id)
                return None

        logger.warning("No refresh callback registered for %s", exchange_id)
        return None

    async def needs_refresh(self, exchange_id: str, token_type: TokenType) -> bool:
        """Check if a token needs refreshing."""
        token = self._tokens.get(exchange_id, {}).get(token_type)
        if token is None:
            return False
        if token.expires_at is None:
            return False
        remaining = (token.expires_at - datetime.now(timezone.utc)).total_seconds()
        return remaining < self.refresh_before_expiry

    async def revoke_all(self, exchange_id: str) -> None:
        """Revoke all tokens for an exchange."""
        async with self._lock:
            self._tokens.pop(exchange_id, None)
        logger.info("All tokens revoked for %s", exchange_id)

    async def get_summary(self) -> dict[str, Any]:
        """Get token summary."""
        total = sum(len(tokens) for tokens in self._tokens.values())
        active = 0
        for exchange_tokens in self._tokens.values():
            for token in exchange_tokens.values():
                if not token.is_expired:
                    active += 1

        return {
            "total_tokens": total,
            "active_tokens": active,
            "exchanges": list(self._tokens.keys()),
        }
