"""
Local KMS provider for development.

Provides a local in-memory KMS
implementation for development and
testing purposes. Uses AES-256-GCM
for key encryption.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from ..config import KMSConfig
from ..constants import AlgorithmName
from ..exceptions import CryptoKMSError, CryptoKeyError
from .provider import KMSKeyInfo, KMSProvider

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class LocalKMSProvider(KMSProvider):
    """
    Local KMS provider for development.

    Implements KMS operations in-memory
    using AES-256-GCM for key encryption.
    Suitable for development, testing, and
    local deployments.

    Warning: Keys are stored in memory only
    and will be lost on restart.
    """

    def __init__(self, config: KMSConfig | None = None) -> None:
        super().__init__(config or KMSConfig())
        self._name = "local"
        self._lock = threading.RLock()
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._master_key: bytes = AESGCM.generate_key(bit_length=256) if _HAS_CRYPTO else os.urandom(32)

    async def initialize(self) -> None:
        """Initialize local KMS (no-op for local)."""
        self._initialized = True
        logger.info("LocalKMSProvider initialized")

    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Encrypt a data key with AES-256-GCM."""
        try:
            nonce = os.urandom(12)
            aesgcm = AESGCM(self._master_key)
            encrypted = aesgcm.encrypt(nonce, data_key, key_id.encode())
            return nonce + encrypted
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="encrypt_key",
                reason=str(e),
            )

    async def decrypt_key(
        self,
        key_id: str,
        encrypted_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Decrypt an encrypted data key."""
        try:
            if len(encrypted_key) <= 12:
                raise CryptoKMSError(
                    provider=self._name,
                    operation="decrypt_key",
                    reason="Encrypted key too short",
                )

            nonce = encrypted_key[:12]
            ciphertext = encrypted_key[12:]
            aesgcm = AESGCM(self._master_key)
            return aesgcm.decrypt(nonce, ciphertext, key_id.encode())
        except CryptoKMSError:
            raise
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="decrypt_key",
                reason=str(e),
            )

    async def generate_key(
        self,
        key_id: str,
        algorithm: str = "",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Generate a new KMS key."""
        with self._lock:
            if key_id in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="generate",
                    reason="Key already exists",
                )

            algo = algorithm or AlgorithmName.AES_256_GCM.value
            key_info = KMSKeyInfo(
                key_id=key_id,
                version=1,
                algorithm=algo,
                created_at=datetime.utcnow(),
                enabled=True,
                description=kwargs.get("description", ""),
                tags=kwargs.get("tags", {}),
            )

            self._keys[key_id] = {
                "info": key_info,
                "material": os.urandom(32),
            }

            logger.info(
                "Local KMS key generated: %s (algo=%s)", key_id, algo,
            )
            return key_info

    async def rotate_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Rotate a KMS key (create new version)."""
        with self._lock:
            if key_id not in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="rotate",
                    reason="Key not found",
                )

            entry = self._keys[key_id]
            old_info = entry["info"]
            new_version = old_info.version + 1

            new_info = KMSKeyInfo(
                key_id=key_id,
                version=new_version,
                algorithm=old_info.algorithm,
                created_at=datetime.utcnow(),
                enabled=True,
                description=old_info.description,
                tags=old_info.tags,
            )

            # Store old key material under version history
            if "history" not in entry:
                entry["history"] = []
            entry["history"].append({
                "version": old_info.version,
                "material": entry["material"],
                "rotated_at": datetime.utcnow(),
            })

            entry["info"] = new_info
            entry["material"] = os.urandom(32)

            logger.info(
                "Local KMS key rotated: %s -> v%d", key_id, new_version,
            )
            return new_info

    async def delete_key(
        self,
        key_id: str,
        pending_days: int = 30,
        **kwargs: Any,
    ) -> None:
        """Schedule a key for deletion."""
        with self._lock:
            if key_id not in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="delete",
                    reason="Key not found",
                )

            entry = self._keys[key_id]
            entry["info"].enabled = False
            entry["scheduled_deletion"] = datetime.utcnow().isoformat()
            logger.info(
                "Local KMS key deletion scheduled: %s", key_id,
            )

    async def get_key_info(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Get key metadata."""
        with self._lock:
            if key_id not in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="get_info",
                    reason="Key not found",
                )
            return self._keys[key_id]["info"]

    async def list_keys(
        self,
        prefix: str = "",
        **kwargs: Any,
    ) -> List[KMSKeyInfo]:
        """List all keys."""
        with self._lock:
            result = []
            for key_id, entry in self._keys.items():
                if prefix and not key_id.startswith(prefix):
                    continue
                result.append(entry["info"])
            return result

    async def get_key_material(
        self,
        key_id: str,
        version: int = 0,
    ) -> bytes:
        """Get raw key material (local only)."""
        with self._lock:
            if key_id not in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="get_material",
                    reason="Key not found",
                )

            entry = self._keys[key_id]
            if version == 0 or version == entry["info"].version:
                return entry["material"]

            # Look up history
            if "history" in entry:
                for h in reversed(entry["history"]):
                    if h["version"] == version:
                        return h["material"]

            raise CryptoKeyError(
                key_id=key_id,
                operation="get_material",
                reason=f"Version {version} not found",
            )

    def count(self) -> int:
        """Get number of stored keys."""
        return len(self._keys)
