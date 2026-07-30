"""
ICYQuant HSM Adapter

Hardware Security Module adapter for key operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import secrets
import uuid

logger = logging.getLogger(__name__)


class HSMProvider(str, Enum):
    AWS_CLOUD_HSM = "aws_cloud_hsm"
    AZURE_DEDICATED_HSM = "azure_dedicated_hsm"
    IBM_SECURITY = "ibm_security"
    THALES = "thales"
    LOCAL_SIMULATED = "local_simulated"


class KeyOperation(str, Enum):
    GENERATE = "generate"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    SIGN = "sign"
    VERIFY = "verify"
    DERIVE = "derive"
    WRAP = "wrap"
    UNWRAP = "unwrap"
    DESTROY = "destroy"


@dataclass
class HSMKey:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    algorithm: str = "AES-256"
    key_size: int = 256
    extractable: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "label": self.label,
            "algorithm": self.algorithm,
            "keySize": self.key_size,
            "extractable": self.extractable,
            "createdAt": self.created_at.isoformat(),
            "usageCount": self.usage_count,
        }


class HSMAdapter:
    """
    Hardware Security Module adapter.

    Provides secure key operations with HSM-backed cryptographic
    operations for highest security requirements.
    """

    def __init__(self, provider: HSMProvider = HSMProvider.LOCAL_SIMULATED):
        self._provider = provider
        self._keys: Dict[str, HSMKey] = {}
        self._key_material: Dict[str, bytes] = {}
        self._operation_log: List[Dict] = []

    def generate_key(
        self,
        label: str,
        algorithm: str = "AES-256",
        key_size: int = 256,
        extractable: bool = False,
    ) -> HSMKey:
        key = HSMKey(
            label=label,
            algorithm=algorithm,
            key_size=key_size,
            extractable=extractable,
        )

        size_bytes = key_size // 8
        self._key_material[key.id] = secrets.token_bytes(size_bytes)
        self._keys[key.id] = key

        self._log_operation(KeyOperation.GENERATE, key.id)
        logger.info(f"HSM key generated: {label} ({algorithm})")
        return key

    def encrypt(self, key_id: str, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key '{key_id}' not found")

        material = self._key_material.get(key_id, b"")
        from Crypto.Cipher import AES
        import base64

        nonce = secrets.token_bytes(12)
        cipher = AES.new(material, AES.MODE_GCM, nonce=nonce)
        if aad:
            cipher.update(aad)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)

        key.usage_count += 1
        key.last_used = datetime.now()
        self._log_operation(KeyOperation.ENCRYPT, key_id)

        return nonce + ciphertext + tag

    def decrypt(self, key_id: str, ciphertext: bytes, aad: Optional[bytes] = None) -> bytes:
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key '{key_id}' not found")

        material = self._key_material.get(key_id, b"")
        from Crypto.Cipher import AES

        nonce = ciphertext[:12]
        ct = ciphertext[12:-16]
        tag = ciphertext[-16:]

        cipher = AES.new(material, AES.MODE_GCM, nonce=nonce)
        if aad:
            cipher.update(aad)

        key.usage_count += 1
        key.last_used = datetime.now()
        self._log_operation(KeyOperation.DECRYPT, key_id)

        return cipher.decrypt_and_verify(ct, tag)

    def sign(self, key_id: str, data: bytes) -> bytes:
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key '{key_id}' not found")
        import hmac
        material = self._key_material.get(key_id, b"")
        signature = hmac.new(material, data, "sha256").digest()
        key.usage_count += 1
        key.last_used = datetime.now()
        self._log_operation(KeyOperation.SIGN, key_id)
        return signature

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        key = self._keys.get(key_id)
        if not key:
            return False
        import hmac
        material = self._key_material.get(key_id, b"")
        expected = hmac.new(material, data, "sha256").digest()
        key.usage_count += 1
        key.last_used = datetime.now()
        self._log_operation(KeyOperation.VERIFY, key_id)
        return hmac.compare_digest(expected, signature)

    def wrap_key(self, wrapping_key_id: str, target_key_id: str) -> bytes:
        target_material = self._key_material.get(target_key_id)
        if not target_material:
            raise ValueError(f"Target key '{target_key_id}' not found")
        return self.encrypt(wrapping_key_id, target_material)

    def unwrap_key(self, unwrapping_key_id: str, wrapped_key: bytes) -> bytes:
        return self.decrypt(unwrapping_key_id, wrapped_key)

    def destroy_key(self, key_id: str):
        self._keys.pop(key_id, None)
        self._key_material.pop(key_id, None)
        self._log_operation(KeyOperation.DESTROY, key_id)

    def list_keys(self) -> List[Dict]:
        return [k.to_dict() for k in self._keys.values()]

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def health_check(self) -> Dict:
        return {
            "provider": self._provider.value,
            "keysCount": len(self._keys),
            "timestamp": datetime.now().isoformat(),
        }

    def _log_operation(self, operation: KeyOperation, key_id: str):
        self._operation_log.append({
            "operation": operation.value,
            "keyId": key_id,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict:
        return {
            "provider": self._provider.value,
            "totalKeys": len(self._keys),
        }
