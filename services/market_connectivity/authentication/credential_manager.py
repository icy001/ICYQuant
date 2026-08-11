"""
Credential Manager — Manages exchange authentication credentials
with secure storage, rotation, and multi-environment support.

API Key → Secret → Signature → Token → Authenticated Session
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CredentialType(str, Enum):
    API_KEY = "api_key"
    HMAC_SECRET = "hmac_secret"
    RSA_KEY = "rsa_key"
    PASSPHRASE = "passphrase"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    OAUTH = "oauth"


@dataclass
class Credential:
    credential_id: str
    exchange_id: str
    credential_type: CredentialType
    value: str
    secret: str = ""
    passphrase: str = ""
    permissions: list[str] = field(default_factory=list)
    environment: str = "production"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class CredentialManager:
    """
    Manages exchange authentication credentials.

    Provides secure storage, retrieval, rotation, and lifecycle
    management for all types of exchange credentials.

    Usage::

        manager = CredentialManager()
        await manager.initialize()
        await manager.store(Credential(
            "binance_main", "binance", CredentialType.API_KEY,
            value="YOUR_API_KEY", secret="YOUR_SECRET",
        ))
        cred = await manager.get("binance_main")
    """

    def __init__(self) -> None:
        self._credentials: dict[str, Credential] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the credential manager."""
        logger.info("CredentialManager initialized.")

    # ---- CRUD ----

    async def store(self, credential: Credential) -> None:
        """Store a credential securely."""
        async with self._lock:
            self._credentials[credential.credential_id] = credential
        logger.info("Credential stored: %s for %s", credential.credential_id, credential.exchange_id)

    async def get(self, credential_id: str) -> Optional[Credential]:
        """Get a credential by ID."""
        cred = self._credentials.get(credential_id)
        if cred and cred.is_expired:
            logger.warning("Credential %s is expired", credential_id)
            return None
        if cred:
            cred.last_used = datetime.now(timezone.utc)
        return cred

    async def get_for_exchange(
        self, exchange_id: str, credential_type: Optional[CredentialType] = None
    ) -> list[Credential]:
        """Get all active credentials for an exchange."""
        creds = [
            c for c in self._credentials.values()
            if c.exchange_id == exchange_id and c.is_active and not c.is_expired
        ]
        if credential_type:
            creds = [c for c in creds if c.credential_type == credential_type]
        return creds

    async def delete(self, credential_id: str) -> bool:
        """Delete a credential."""
        async with self._lock:
            return self._credentials.pop(credential_id, None) is not None

    async def deactivate(self, credential_id: str) -> bool:
        """Deactivate a credential without deleting."""
        cred = self._credentials.get(credential_id)
        if cred:
            cred.is_active = False
            return True
        return False

    async def rotate(
        self, credential_id: str, new_credential: Credential
    ) -> bool:
        """Rotate a credential (deactivate old, store new)."""
        old = self._credentials.get(credential_id)
        if old:
            old.is_active = False
        await self.store(new_credential)
        logger.info("Credential rotated: %s → %s", credential_id, new_credential.credential_id)
        return True

    async def list_all(self) -> list[Credential]:
        """List all credentials."""
        return list(self._credentials.values())

    async def list_active(self) -> list[Credential]:
        """List all active, non-expired credentials."""
        return [
            c for c in self._credentials.values()
            if c.is_active and not c.is_expired
        ]

    async def get_summary(self) -> dict[str, Any]:
        """Get credential summary."""
        all_creds = list(self._credentials.values())
        active = sum(1 for c in all_creds if c.is_active and not c.is_expired)

        type_counts: dict[str, int] = {}
        for c in all_creds:
            if c.is_active and not c.is_expired:
                type_counts[c.credential_type.value] = type_counts.get(c.credential_type.value, 0) + 1

        return {
            "total": len(all_creds),
            "active": active,
            "expired": sum(1 for c in all_creds if c.is_expired),
            "by_type": type_counts,
        }
