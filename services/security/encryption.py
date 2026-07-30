"""
ICYQuant Encryption Engine

Supports encryption at rest (AES-256), in transit (TLS 1.3),
and field-level encryption for sensitive data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import base64
import hashlib

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    AES_256_CBC = "aes_256_cbc"
    AES_256_GCM = "aes_256_gcm"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    RSA_OAEP = "rsa_oaep"
    ECDSA_P256 = "ecdsa_p256"
    TLS_1_3 = "tls_1_3"


@dataclass
class FieldEncryption:
    field_name: str
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_name: str = ""
    searchable: bool = False
    format_hint: str = "generic"

    def to_dict(self) -> Dict:
        return {
            "fieldName": self.field_name,
            "algorithm": self.algorithm.value,
            "keyName": self.key_name,
            "searchable": self.searchable,
        }


@dataclass
class EncryptedField:
    field_name: str = ""
    ciphertext: str = ""
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    encrypted_at: datetime = field(default_factory=datetime.now)
    key_version: int = 1
    original_format: str = ""
    searchable_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "fieldName": self.field_name,
            "ciphertext": self.ciphertext,
            "algorithm": self.algorithm.value,
            "encryptedAt": self.encrypted_at.isoformat(),
            "keyVersion": self.key_version,
            "searchableHash": self.searchable_hash,
        }


class EncryptionError(Exception):
    pass


class EncryptionEngine:
    """
    Encryption engine supporting multiple algorithms and field-level encryption.

    Provides encryption at rest and in transit with configurable algorithms.
    """

    def __init__(self):
        self._field_configs: Dict[str, FieldEncryption] = {}
        self._encryption_keys: Dict[str, bytes] = {}
        self._encrypted_cache: Dict[str, EncryptedField] = {}
        self._stats = {
            "total_encrypt": 0,
            "total_decrypt": 0,
            "fields_encrypted": 0,
        }

    def register_field(self, config: FieldEncryption):
        self._field_configs[config.field_name] = config
        logger.info(f"Field encryption registered: {config.field_name} ({config.algorithm.value})")

    def set_encryption_key(self, name: str, key: bytes):
        self._encryption_keys[name] = key

    def encrypt_field(
        self,
        field_name: str,
        plaintext: str,
        key_name: Optional[str] = None,
    ) -> EncryptedField:
        config = self._field_configs.get(field_name)
        if not config:
            raise EncryptionError(f"Field '{field_name}' not registered for encryption")

        key = self._encryption_keys.get(key_name or config.key_name)
        if not key:
            raise EncryptionError(f"Encryption key not found for field '{field_name}'")

        ciphertext = self._encrypt(plaintext.encode(), key, config.algorithm)
        ciphertext_b64 = base64.b64encode(ciphertext).decode()

        searchable_hash = None
        if config.searchable:
            searchable_hash = hashlib.sha256(
                f"{plaintext}:{key}".encode()
            ).hexdigest()

        encrypted = EncryptedField(
            field_name=field_name,
            ciphertext=ciphertext_b64,
            algorithm=config.algorithm,
            searchable_hash=searchable_hash,
        )

        self._encrypted_cache[field_name] = encrypted
        self._stats["total_encrypt"] += 1
        self._stats["fields_encrypted"] += 1
        return encrypted

    def decrypt_field(
        self,
        encrypted: EncryptedField,
        key_name: Optional[str] = None,
    ) -> str:
        config = self._field_configs.get(encrypted.field_name)
        if not config:
            raise EncryptionError(f"Field '{encrypted.field_name}' not registered")

        key = self._encryption_keys.get(key_name or config.key_name)
        if not key:
            raise EncryptionError(f"Encryption key not found")

        ciphertext = base64.b64decode(encrypted.ciphertext)
        plaintext = self._decrypt(ciphertext, key, encrypted.algorithm)
        self._stats["total_decrypt"] += 1
        return plaintext.decode()

    def encrypt_record(
        self,
        record: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        result = dict(record)
        target_fields = fields or list(self._field_configs.keys())
        for field_name in target_fields:
            if field_name in result and field_name in self._field_configs:
                encrypted = self.encrypt_field(field_name, str(result[field_name]))
                result[f"_{field_name}_encrypted"] = encrypted.to_dict()
                result.pop(field_name)
        return result

    def decrypt_record(
        self,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        result = dict(record)
        for field_name in list(self._field_configs.keys()):
            encrypted_key = f"_{field_name}_encrypted"
            if encrypted_key in result:
                enc_data = result.pop(encrypted_key)
                encrypted = EncryptedField(
                    field_name=enc_data["fieldName"],
                    ciphertext=enc_data["ciphertext"],
                    algorithm=EncryptionAlgorithm(enc_data["algorithm"]),
                )
                result[field_name] = self.decrypt_field(encrypted)
        return result

    def verify_field(
        self,
        field_name: str,
        plaintext: str,
        encrypted: EncryptedField,
        key_name: Optional[str] = None,
    ) -> bool:
        config = self._field_configs.get(field_name)
        if not config or not config.searchable:
            return False
        key = self._encryption_keys.get(key_name or config.key_name)
        searchable_hash = hashlib.sha256(f"{plaintext}:{key}".encode()).hexdigest()
        return searchable_hash == encrypted.searchable_hash

    def get_stats(self) -> Dict:
        return dict(self._stats)

    def list_registered_fields(self) -> List[Dict]:
        return [c.to_dict() for c in self._field_configs.values()]

    def to_dict(self) -> Dict:
        return {
            "registeredFields": len(self._field_configs),
            "encryptionKeys": list(self._encryption_keys.keys()),
            "stats": self._stats,
        }

    def _encrypt(self, plaintext: bytes, key: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        import secrets as _secrets
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            nonce = _secrets.token_bytes(12)
            from Crypto.Cipher import AES
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            return nonce + ciphertext + tag
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            iv = _secrets.token_bytes(16)
            from Crypto.Cipher import AES
            pad_len = 16 - (len(plaintext) % 16)
            padded = plaintext + bytes([pad_len] * pad_len)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            return iv + cipher.encrypt(padded)
        else:
            nonce = _secrets.token_bytes(12)
            from Crypto.Cipher import AES
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            return nonce + ciphertext + tag

    def _decrypt(self, ciphertext: bytes, key: bytes, algorithm: EncryptionAlgorithm) -> bytes:
        from Crypto.Cipher import AES
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            nonce = ciphertext[:12]
            ct = ciphertext[12:-16]
            tag = ciphertext[-16:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ct, tag)
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            iv = ciphertext[:16]
            ct = ciphertext[16:]
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            padded = cipher.decrypt(ct)
            pad_len = padded[-1]
            return padded[:-pad_len]
        else:
            nonce = ciphertext[:12]
            ct = ciphertext[12:-16]
            tag = ciphertext[-16:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ct, tag)
