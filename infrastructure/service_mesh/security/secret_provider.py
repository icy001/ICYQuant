"""Secret provider for ICYQuant Service Mesh.

Provides ``SecretProvider`` for integrating with the Secrets Platform
to supply TLS keys, private keys, and root CA certificates.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import SecretError

logger = logging.getLogger(__name__)


class SecretRecord:
    """A secret record."""

    def __init__(
        self,
        secret_id: str,
        secret_type: str = "tls_key",
        value: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.secret_id = secret_id
        self.secret_type = secret_type
        self._value = value or f"secret-{secret_id}"
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.access_count = 0

    def access(self) -> str:
        self.access_count += 1
        return self._value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "secret_id": self.secret_id,
            "secret_type": self.secret_type,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
        }


class SecretProvider:
    """Provides secrets from the Secrets Platform."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._secrets: Dict[str, SecretRecord] = {}
        self._access_count = 0
        self._started = False

    def store(self, secret_id: str, secret_type: str = "tls_key", value: str = "", metadata: Optional[Dict[str, Any]] = None) -> SecretRecord:
        secret = SecretRecord(secret_id, secret_type, value, metadata)
        with self._lock:
            self._secrets[secret_id] = secret
        logger.info("Secret stored: %s (type: %s)", secret_id, secret_type)
        return secret

    def get(self, secret_id: str) -> str:
        with self._lock:
            secret = self._secrets.get(secret_id)
            self._access_count += 1
        if not secret:
            raise SecretError(f"Secret not found: {secret_id}")
        return secret.access()

    def get_record(self, secret_id: str) -> Optional[SecretRecord]:
        with self._lock:
            return self._secrets.get(secret_id)

    def remove(self, secret_id: str) -> bool:
        with self._lock:
            if secret_id in self._secrets:
                del self._secrets[secret_id]
                return True
            return False

    def list_secrets(self, secret_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            secrets = list(self._secrets.values())
        if secret_type:
            secrets = [s for s in secrets if s.secret_type == secret_type]
        return [s.to_dict() for s in secrets]

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_secrets": len(self._secrets),
                "access_count": self._access_count,
                "started": self._started,
            }
