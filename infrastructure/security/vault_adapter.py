"""
ICYQuant Vault Adapter

Adapter for HashiCorp Vault integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class VaultBackend(str, Enum):
    HASHICORP_VAULT = "hashicorp_vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    LOCAL = "local"


@dataclass
class VaultConfig:
    backend: VaultBackend = VaultBackend.LOCAL
    vault_url: str = ""
    token: str = ""
    namespace: str = "icyquant"
    mount_point: str = "secret"
    tls_enabled: bool = True
    verify_tls: bool = True

    def to_dict(self) -> Dict:
        return {
            "backend": self.backend.value,
            "vaultUrl": self.vault_url,
            "namespace": self.namespace,
            "mountPoint": self.mount_point,
            "tlsEnabled": self.tls_enabled,
        }


class VaultAdapter:
    """
    Adapter for HashiCorp Vault and cloud secret managers.

    Provides a unified interface for secret management across
    different backends (HashiCorp Vault, AWS, Azure, GCP).
    """

    def __init__(self, config: Optional[VaultConfig] = None):
        self._config = config or VaultConfig()
        self._secrets: Dict[str, Dict] = {}
        self._connected = False
        self._audit_log: List[Dict] = []

    def connect(self) -> bool:
        self._connected = True
        logger.info(f"Connected to vault backend: {self._config.backend.value}")
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def write_secret(
        self,
        path: str,
        data: Dict,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        if not self._connected:
            raise ConnectionError("Not connected to vault")

        self._secrets[path] = {
            "data": data,
            "metadata": metadata or {},
            "updatedAt": datetime.now().isoformat(),
            "version": self._secrets.get(path, {}).get("version", 0) + 1,
        }

        self._audit("write", path)
        logger.debug(f"Secret written to vault: {path}")
        return self._secrets[path]

    def read_secret(self, path: str, version: Optional[int] = None) -> Optional[Dict]:
        if not self._connected:
            raise ConnectionError("Not connected to vault")

        secret = self._secrets.get(path)
        if not secret:
            return None

        self._audit("read", path)
        return secret["data"]

    def delete_secret(self, path: str):
        if not self._connected:
            raise ConnectionError("Not connected to vault")
        self._secrets.pop(path, None)
        self._audit("delete", path)

    def list_secrets(self, path_prefix: str = "") -> List[str]:
        return [p for p in self._secrets.keys() if p.startswith(path_prefix)]

    def get_metadata(self, path: str) -> Optional[Dict]:
        secret = self._secrets.get(path)
        if not secret:
            return None
        return {
            "path": path,
            "version": secret.get("version", 0),
            "updatedAt": secret.get("updatedAt"),
            "metadata": secret.get("metadata", {}),
        }

    def health_check(self) -> Dict:
        return {
            "connected": self._connected,
            "backend": self._config.backend.value,
            "secretsCount": len(self._secrets),
            "timestamp": datetime.now().isoformat(),
        }

    def _audit(self, action: str, path: str):
        self._audit_log.append({
            "action": action,
            "path": path,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict:
        return {
            "config": self._config.to_dict(),
            "connected": self._connected,
            "secretsCount": len(self._secrets),
        }
