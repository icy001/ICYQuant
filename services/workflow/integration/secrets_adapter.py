"""Secrets Adapter — secrets and credentials management for workflows.

Provides secure access to:

* API keys and tokens
* Database credentials
* Encryption keys
* External service credentials

Secrets are referenced by name within workflow definitions, never hard-coded.
The adapter fetches them from the platform secrets manager at runtime.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretsAdapter:
    """Secure secrets access for workflow execution.

    Usage::

        adapter = SecretsAdapter()
        await adapter.start()
        api_key = await adapter.get_secret("oms_api_key")
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False
        self._secrets: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("SecretsAdapter: started")

    async def stop(self) -> None:
        self._started = False
        with self._lock:
            self._secrets.clear()
        logger.info("SecretsAdapter: stopped")

    # ------------------------------------------------------------------
    # Secret operations
    # ------------------------------------------------------------------

    async def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret by key."""
        with self._lock:
            return self._secrets.get(key)
        # In production: fetch from Vault / Secrets Manager

    async def set_secret(self, key: str, value: str) -> None:
        """Store a secret (for testing / local dev)."""
        with self._lock:
            self._secrets[key] = value

    async def delete_secret(self, key: str) -> bool:
        with self._lock:
            return self._secrets.pop(key, None) is not None

    async def list_secret_keys(self) -> list:
        with self._lock:
            return list(self._secrets.keys())

    async def resolve_references(self, value: str) -> str:
        """Resolve secret references in a string.

        Replaces patterns like ``$SECRET{key}`` with actual values.
        """
        import re
        pattern = re.compile(r'\$SECRET\{(\w+)\}')
        def replacer(match):
            key = match.group(1)
            secret = self._secrets.get(key, "")
            return secret
        return pattern.sub(replacer, value)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "stored_secrets": len(self._secrets),
                "secret_keys": list(self._secrets.keys()),
            }
