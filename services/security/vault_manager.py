"""
ICYQuant Vault Manager

Unified secret management with support for HashiCorp Vault integration.
Manages API keys, database credentials, JWT secrets, TLS certificates, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import hashlib
import base64
import secrets

logger = logging.getLogger(__name__)


class SecretScope(str, Enum):
    API_KEY = "api_key"
    DATABASE = "database"
    BROKER = "broker"
    JWT = "jwt"
    SSH_KEY = "ssh_key"
    TLS_CERT = "tls_cert"
    ENCRYPTION_KEY = "encryption_key"
    SERVICE = "service"
    CLOUD_CREDENTIAL = "cloud_credential"


@dataclass
class SecretMetadata:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    scope: SecretScope = SecretScope.API_KEY
    description: str = ""
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_rotated: Optional[datetime] = None
    next_rotation: Optional[datetime] = None
    rotation_interval_days: int = 90
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    versions: List[Dict] = field(default_factory=list)
    current_version: int = 1
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def needs_rotation(self) -> bool:
        if not self.next_rotation:
            return True
        return datetime.now() >= self.next_rotation

    def record_access(self):
        self.access_count += 1
        self.last_accessed = datetime.now()

    def record_rotation(self, version: int):
        self.last_rotated = datetime.now()
        self.next_rotation = datetime.now() + timedelta(days=self.rotation_interval_days)
        self.current_version = version
        self.versions.append({
            "version": version,
            "rotatedAt": self.last_rotated.isoformat(),
        })

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "scope": self.scope.value,
            "description": self.description,
            "owner": self.owner,
            "createdAt": self.created_at.isoformat(),
            "lastRotated": self.last_rotated.isoformat() if self.last_rotated else None,
            "nextRotation": self.next_rotation.isoformat() if self.next_rotation else None,
            "rotationIntervalDays": self.rotation_interval_days,
            "currentVersion": self.current_version,
            "accessCount": self.access_count,
            "needsRotation": self.needs_rotation(),
        }


class VaultError(Exception):
    pass


class VaultManager:
    """
    Unified secret management service.

    Provides CRUD operations for secrets with rotation tracking,
    access auditing, and scope-based organization.
    """

    def __init__(self):
        self._secrets: Dict[str, SecretMetadata] = {}
        self._values: Dict[str, Dict[int, str]] = {}
        self._audit_log: List[Dict] = []
        self._max_audit_size = 50000
        self._encryption_key = secrets.token_bytes(32)

    def create_secret(
        self,
        name: str,
        value: str,
        scope: SecretScope,
        owner: str = "",
        description: str = "",
        rotation_interval_days: int = 90,
        tags: Optional[List[str]] = None,
    ) -> SecretMetadata:
        if name in self._secrets:
            raise VaultError(f"Secret '{name}' already exists")

        if isinstance(scope, str):
            scope = SecretScope(scope)

        metadata = SecretMetadata(
            name=name,
            scope=scope,
            owner=owner,
            description=description,
            rotation_interval_days=rotation_interval_days,
            tags=tags or [],
        )
        metadata.next_rotation = datetime.now() + timedelta(days=rotation_interval_days)

        self._secrets[name] = metadata
        self._values[name] = {1: self._encrypt_value(value)}
        metadata.versions.append({"version": 1, "rotatedAt": datetime.now().isoformat()})

        self._audit("create", name, owner)
        logger.info(f"Secret created: {name} (scope: {scope.value})")
        return metadata

    def get_secret(self, name: str, version: Optional[int] = None) -> Optional[str]:
        metadata = self._secrets.get(name)
        if not metadata:
            return None

        versions = self._values.get(name, {})
        ver = version or metadata.current_version
        encrypted = versions.get(ver)
        if not encrypted:
            return None

        metadata.record_access()
        self._audit("read", name, metadata.owner)
        return self._decrypt_value(encrypted)

    def update_secret(self, name: str, value: str) -> Optional[SecretMetadata]:
        metadata = self._secrets.get(name)
        if not metadata:
            return None

        new_version = metadata.current_version + 1
        self._values[name][new_version] = self._encrypt_value(value)
        metadata.record_rotation(new_version)

        self._audit("rotate", name, metadata.owner)
        logger.info(f"Secret rotated: {name} -> v{new_version}")
        return metadata

    def rotate_if_needed(self, name: str) -> Optional[SecretMetadata]:
        metadata = self._secrets.get(name)
        if not metadata or not metadata.needs_rotation():
            return metadata
        current_value = self.get_secret(name)
        if current_value:
            return self.update_secret(name, current_value)
        return metadata

    def delete_secret(self, name: str):
        if name not in self._secrets:
            raise VaultError(f"Secret '{name}' not found")
        del self._secrets[name]
        del self._values[name]
        self._audit("delete", name, "")
        logger.info(f"Secret deleted: {name}")

    def list_secrets(
        self,
        scope: Optional[SecretScope] = None,
        owner: Optional[str] = None,
    ) -> List[SecretMetadata]:
        secrets = list(self._secrets.values())
        if scope:
            secrets = [s for s in secrets if s.scope == scope]
        if owner:
            secrets = [s for s in secrets if s.owner == owner]
        return secrets

    def get_metadata(self, name: str) -> Optional[SecretMetadata]:
        return self._secrets.get(name)

    def get_rotation_candidates(self) -> List[SecretMetadata]:
        return [s for s in self._secrets.values() if s.needs_rotation()]

    def bulk_rotate(self) -> List[Dict]:
        candidates = self.get_rotation_candidates()
        results = []
        for secret in candidates:
            meta = self.update_secret(secret.name, self.get_secret(secret.name))
            results.append({
                "name": secret.name,
                "rotated": meta.current_version if meta else None,
            })
        return results

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        return self._audit_log[-limit:]

    def to_dict(self) -> Dict:
        return {
            "totalSecrets": len(self._secrets),
            "byScope": self._count_by_scope(),
            "rotationCandidates": len(self.get_rotation_candidates()),
            "auditEntries": len(self._audit_log),
        }

    def _count_by_scope(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for secret in self._secrets.values():
            key = secret.scope.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _encrypt_value(self, value: str) -> str:
        iv = secrets.token_bytes(16)
        cipher = bytearray()
        key = self._encryption_key
        for i, ch in enumerate(value.encode()):
            cipher.append(ch ^ key[i % len(key)] ^ iv[i % len(iv)])
        return base64.b64encode(iv + bytes(cipher)).decode()

    def _decrypt_value(self, encrypted: str) -> str:
        data = base64.b64decode(encrypted)
        iv = data[:16]
        cipher = data[16:]
        key = self._encryption_key
        plain = bytearray()
        for i, b in enumerate(cipher):
            plain.append(b ^ key[i % len(key)] ^ iv[i % len(iv)])
        return plain.decode()

    def _audit(self, action: str, name: str, actor: str):
        self._audit_log.append({
            "action": action,
            "secretName": name,
            "actor": actor,
            "timestamp": datetime.now().isoformat(),
            "traceId": str(uuid.uuid4())[:12],
        })
        if len(self._audit_log) > self._max_audit_size:
            self._audit_log = self._audit_log[-self._max_audit_size:]
