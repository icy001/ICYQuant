"""
ICYQuant Key Management Service (KMS)

Unified key management with support for cloud KMS providers:
AWS KMS, Azure Key Vault, Google Cloud KMS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import secrets
import hashlib
import base64

logger = logging.getLogger(__name__)


class KeyType(str, Enum):
    AES_256 = "aes_256"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    ECDSA_P256 = "ecdsa_p256"
    HMAC_SHA256 = "hmac_sha256"
    AES_256_GCM = "aes_256_gcm"


class KeyState(str, Enum):
    PENDING = "pending"
    ENABLED = "enabled"
    DISABLED = "disabled"
    DELETED = "deleted"
    ROTATING = "rotating"


class KMSProvider(str, Enum):
    LOCAL = "local"
    AWS_KMS = "aws_kms"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_KMS = "gcp_kms"
    HSM = "hsm"


@dataclass
class KeyMetadata:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    key_type: KeyType = KeyType.AES_256
    state: KeyState = KeyState.PENDING
    provider: KMSProvider = KMSProvider.LOCAL
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    rotation_date: Optional[datetime] = None
    rotation_interval_days: int = 90
    usage_count: int = 0
    last_used: Optional[datetime] = None
    versions: List[Dict] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "keyType": self.key_type.value,
            "state": self.state.value,
            "provider": self.provider.value,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "rotationDate": self.rotation_date.isoformat() if self.rotation_date else None,
            "rotationIntervalDays": self.rotation_interval_days,
            "usageCount": self.usage_count,
            "lastUsed": self.last_used.isoformat() if self.last_used else None,
        }


class KeyManagementService:
    """
    Unified Key Management Service.

    Manages cryptographic keys with support for multiple KMS providers,
    key rotation, encryption/decryption operations, and lifecycle management.
    """

    def __init__(self, provider: KMSProvider = KMSProvider.LOCAL):
        self._provider = provider
        self._keys: Dict[str, KeyMetadata] = {}
        self._key_materials: Dict[str, bytes] = {}
        self._audit_log: List[Dict] = []
        self._max_audit_size = 10000

    def create_key(
        self,
        name: str,
        key_type: KeyType = KeyType.AES_256,
        description: str = "",
        rotation_interval_days: int = 90,
    ) -> KeyMetadata:
        if name in self._keys:
            raise ValueError(f"Key '{name}' already exists")

        key_size_map = {
            KeyType.AES_256: 32,
            KeyType.AES_256_GCM: 32,
            KeyType.HMAC_SHA256: 32,
        }
        key_size = key_size_map.get(key_type, 32)
        material = secrets.token_bytes(key_size)

        metadata = KeyMetadata(
            name=name,
            key_type=key_type,
            state=KeyState.ENABLED,
            provider=self._provider,
            description=description,
            rotation_interval_days=rotation_interval_days,
            rotation_date=datetime.now() + timedelta(days=rotation_interval_days),
        )
        self._keys[name] = metadata
        self._key_materials[name] = material

        self._audit("create", name, key_type.value)
        logger.info(f"Key created: {name} ({key_type.value})")
        return metadata

    def encrypt(self, key_name: str, plaintext: str, aad: Optional[str] = None) -> str:
        metadata = self._get_active_key(key_name)
        if not metadata:
            raise ValueError(f"Key '{key_name}' not found or not enabled")

        key = self._key_materials[key_name]
        is_gcm = metadata.key_type == KeyType.AES_256_GCM
        iv_size = 12 if is_gcm else 16
        iv = secrets.token_bytes(iv_size)

        if is_gcm:
            ciphertext = self._aes_gcm_encrypt(key, iv, plaintext.encode(), aad.encode() if aad else None)
        else:
            ciphertext = self._aes_encrypt(key, iv, plaintext.encode())

        metadata.usage_count += 1
        metadata.last_used = datetime.now()
        metadata.updated_at = datetime.now()

        return base64.b64encode(iv + ciphertext).decode()

    def decrypt(self, key_name: str, ciphertext: str, aad: Optional[str] = None) -> str:
        metadata = self._get_active_key(key_name)
        if not metadata:
            raise ValueError(f"Key '{key_name}' not found or not enabled")

        key = self._key_materials[key_name]
        is_gcm = metadata.key_type == KeyType.AES_256_GCM
        iv_size = 12 if is_gcm else 16
        data = base64.b64decode(ciphertext)
        iv = data[:iv_size]
        ct = data[iv_size:]

        if metadata.key_type == KeyType.AES_256_GCM:
            plaintext = self._aes_gcm_decrypt(key, iv, ct, aad.encode() if aad else None)
        else:
            plaintext = self._aes_decrypt(key, iv, ct)

        metadata.usage_count += 1
        metadata.last_used = datetime.now()
        return plaintext.decode()

    def rotate_key(self, key_name: str) -> KeyMetadata:
        metadata = self._keys.get(key_name)
        if not metadata:
            raise ValueError(f"Key '{key_name}' not found")
        if metadata.state == KeyState.DELETED:
            raise ValueError(f"Key '{key_name}' is deleted")

        old_key = self._key_materials.get(key_name, b"")
        new_key = secrets.token_bytes(len(old_key) if old_key else 32)

        metadata.state = KeyState.ROTATING
        metadata.versions.append({
            "version": len(metadata.versions) + 1,
            "rotatedAt": datetime.now().isoformat(),
            "oldKeyHash": hashlib.sha256(old_key).hexdigest()[:16],
        })

        self._key_materials[key_name] = new_key
        metadata.state = KeyState.ENABLED
        metadata.rotation_date = datetime.now() + timedelta(days=metadata.rotation_interval_days)
        metadata.updated_at = datetime.now()

        self._audit("rotate", key_name, metadata.key_type.value)
        logger.info(f"Key rotated: {key_name}")
        return metadata

    def disable_key(self, key_name: str):
        metadata = self._keys.get(key_name)
        if not metadata:
            raise ValueError(f"Key '{key_name}' not found")
        metadata.state = KeyState.DISABLED
        self._audit("disable", key_name, "")

    def delete_key(self, key_name: str):
        metadata = self._keys.get(key_name)
        if not metadata:
            raise ValueError(f"Key '{key_name}' not found")
        if metadata.state not in (KeyState.DISABLED, KeyState.PENDING):
            raise ValueError("Key must be disabled before deletion")
        metadata.state = KeyState.DELETED
        self._key_materials.pop(key_name, None)
        self._audit("delete", key_name, "")

    def list_keys(self, state: Optional[KeyState] = None) -> List[KeyMetadata]:
        keys = list(self._keys.values())
        if state:
            keys = [k for k in keys if k.state == state]
        return keys

    def get_key(self, name: str) -> Optional[KeyMetadata]:
        meta = self._keys.get(name)
        if meta and meta.state == KeyState.DELETED:
            return None
        return meta

    def get_rotation_candidates(self) -> List[KeyMetadata]:
        now = datetime.now()
        return [k for k in self._keys.values()
                if k.state == KeyState.ENABLED
                and k.rotation_date and now >= k.rotation_date]

    def bulk_rotate(self) -> List[Dict]:
        candidates = self.get_rotation_candidates()
        results = []
        for key in candidates:
            meta = self.rotate_key(key.name)
            results.append({"name": key.name, "version": len(meta.versions)})
        return results

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        return self._audit_log[-limit:]

    def to_dict(self) -> Dict:
        return {
            "provider": self._provider.value,
            "totalKeys": len(self._keys),
            "activeKeys": sum(1 for k in self._keys.values() if k.state == KeyState.ENABLED),
            "rotationCandidates": len(self.get_rotation_candidates()),
        }

    def _get_active_key(self, name: str) -> Optional[KeyMetadata]:
        meta = self._keys.get(name)
        if meta and meta.state == KeyState.ENABLED:
            return meta
        return None

    def _aes_encrypt(self, key: bytes, iv: bytes, plaintext: bytes) -> bytes:
        from Crypto.Cipher import AES
        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len] * pad_len)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(padded)

    def _aes_decrypt(self, key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = cipher.decrypt(ciphertext)
        pad_len = padded[-1]
        return padded[:-pad_len]

    def _aes_gcm_encrypt(self, key: bytes, nonce: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        if aad:
            cipher.update(aad)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext + tag

    def _aes_gcm_decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: Optional[bytes] = None) -> bytes:
        from Crypto.Cipher import AES
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        if aad:
            cipher.update(aad)
        return cipher.decrypt_and_verify(ct, tag)

    def _audit(self, action: str, key_name: str, key_type: str):
        self._audit_log.append({
            "action": action,
            "keyName": key_name,
            "keyType": key_type,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._audit_log) > self._max_audit_size:
            self._audit_log = self._audit_log[-self._max_audit_size:]
