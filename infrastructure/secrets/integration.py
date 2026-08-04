"""
Crypto-Secrets integration bridge.

Bridges CryptoService and SecretsManager to provide
transparent encryption/decryption of secrets using
envelope encryption with KMS integration.

Architecture:
    Application
          |
    CryptoSecretsIntegration
          |
    +---> CryptoService (encryption/decryption)
    +---> SecretsManager (secure storage)
    +---> Crypto Key Mapping (secret_key -> crypto_key_id)

Usage:
    from infrastructure.crypto import CryptoService
    from infrastructure.secrets import SecretsManager
    from infrastructure.secrets.integration import CryptoSecretsIntegration

    crypto = CryptoService()
    secrets = SecretsManager()
    integration = CryptoSecretsIntegration(
        crypto_service=crypto,
        secrets_manager=secrets,
        key_mapping={"db_password": "my-kms-key-id"},
    )
    encrypted = await integration.encrypt_secret(
        "db_password", "super-secret-value"
    )
    decrypted = await integration.decrypt_secret("db_password")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from infrastructure.crypto import (
    CryptoDecryptionError,
    CryptoEncryptionError,
    CryptoService,
)
from infrastructure.crypto.pipeline.encrypt import EncryptionResult
from infrastructure.crypto.pipeline.decrypt import DecryptionResult
from infrastructure.secrets import (
    SecretEncryptionError,
    SecretNotFoundError,
    SecretsManager,
)

logger = logging.getLogger(__name__)


class CryptoSecretsIntegration:
    """
    Bridge between CryptoService and SecretsManager.

    Provides transparent encryption and decryption
    of secrets using the envelope encryption capabilities
    of CryptoService, with secure storage handled by
    SecretsManager.

    Features:
    - Encrypt values with crypto, store encrypted in secrets
    - Read encrypted secrets, decrypt with crypto
    - Rotate encrypted secrets with crypto key rotation
    - Batch encrypt/decrypt multiple secrets
    - Verify encrypted secret integrity
    - Crypto key mapping (secret_key -> crypto_key_id)
    - Fallback to plaintext if crypto unavailable
    - Thread-safe operations
    - Envelope encryption integration

    Usage:
        integration = CryptoSecretsIntegration(
            crypto_service=crypto,
            secrets_manager=secrets,
            key_mapping={"secret_key": "crypto_key_id"},
        )
        await integration.encrypt_secret("secret_key", "value")
        value = await integration.decrypt_secret("secret_key")
    """

    def __init__(
        self,
        crypto_service: CryptoService,
        secrets_manager: SecretsManager,
        key_mapping: Optional[Dict[str, str]] = None,
        default_key_id: str = "",
        fallback_to_plaintext: bool = True,
    ) -> None:
        """
        Initialize integration bridge.

        Args:
            crypto_service: CryptoService instance for
                encryption/decryption operations.
            secrets_manager: SecretsManager instance for
                secure secret storage.
            key_mapping: Maps secret keys to crypto key IDs.
                Example: {"db_password": "kms-key-1"}
            default_key_id: Default crypto key ID used when
                no mapping is found for a secret key.
            fallback_to_plaintext: If True, falls back to
                storing plaintext when crypto is unavailable.
        """
        self._crypto = crypto_service
        self._secrets = secrets_manager
        self._key_mapping = key_mapping or {}
        self._default_key_id = default_key_id
        self._fallback_to_plaintext = fallback_to_plaintext
        self._lock = asyncio.Lock()

        self._stats: Dict[str, Any] = {
            "encrypt_operations": 0,
            "decrypt_operations": 0,
            "rotate_operations": 0,
            "batch_encrypt_operations": 0,
            "batch_decrypt_operations": 0,
            "verify_operations": 0,
            "fallback_count": 0,
            "errors": 0,
            "total_duration_ms": 0.0,
        }

    def get_crypto_key_id(self, secret_key: str) -> str:
        """
        Get the crypto key ID for a secret key.

        Resolves the crypto key ID from the key mapping,
        falling back to the default key ID if no mapping
        exists.

        Args:
            secret_key: The secret key to look up.

        Returns:
            Crypto key ID string.

        Raises:
            KeyError: If no mapping or default key ID exists.
        """
        key_id = self._key_mapping.get(secret_key)
        if key_id:
            return key_id
        if self._default_key_id:
            return self._default_key_id
        raise KeyError(
            f"No crypto key ID mapped for secret key: {secret_key}"
        )

    def register_key_mapping(
        self,
        secret_key: str,
        crypto_key_id: str,
    ) -> None:
        """
        Register a mapping from secret key to crypto key ID.

        Args:
            secret_key: The secret key.
            crypto_key_id: The crypto key ID to use.
        """
        self._key_mapping[secret_key] = crypto_key_id

    def remove_key_mapping(self, secret_key: str) -> None:
        """
        Remove a key mapping.

        Args:
            secret_key: The secret key to unmap.
        """
        self._key_mapping.pop(secret_key, None)

    def set_default_key_id(self, key_id: str) -> None:
        """
        Set the default crypto key ID.

        Args:
            key_id: Default crypto key ID.
        """
        self._default_key_id = key_id

    @property
    def key_mapping(self) -> Dict[str, str]:
        """Get a copy of the current key mapping."""
        return dict(self._key_mapping)

    async def encrypt_secret(
        self,
        secret_key: str,
        value: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Encrypt a secret value and store it encrypted.

        Uses CryptoService to encrypt the value, then stores
        the encrypted payload as a JSON-serialized
        EncryptionResult in SecretsManager.

        Args:
            secret_key: The secret key identifier.
            value: The plaintext value to encrypt and store.
            namespace: The secrets namespace.

        Returns:
            Dict with operation result including:
                - success: Whether encryption succeeded
                - secret_key: The secret key
                - namespace: The namespace used
                - encrypted: The encrypted payload dict
                - fallback: Whether plaintext fallback was used

        Raises:
            SecretEncryptionError: If encryption fails and
                fallback is disabled or also fails.
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["encrypt_operations"] += 1

        crypto_key_id = self.get_crypto_key_id(secret_key)

        try:
            data_bytes = value.encode("utf-8")
            encrypted_result = await self._crypto.encrypt(
                data=data_bytes,
                key_id=crypto_key_id,
            )

            encrypted_payload = encrypted_result.to_dict()
            encrypted_payload["_integration"] = "CryptoSecretsIntegration"
            encrypted_payload["_version"] = 1

            stored_value = json.dumps(encrypted_payload)

            item = await self._secrets.set(
                key=secret_key,
                value=stored_value,
                namespace=namespace,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            async with self._lock:
                self._stats["total_duration_ms"] += duration_ms

            logger.info(
                "Encrypted secret '%s' in namespace '%s' "
                "with crypto key '%s'",
                secret_key, namespace, crypto_key_id,
            )

            return {
                "success": True,
                "secret_key": secret_key,
                "namespace": namespace,
                "encrypted": encrypted_payload,
                "fallback": False,
                "duration_ms": duration_ms,
            }

        except (CryptoEncryptionError, RuntimeError) as e:
            logger.warning(
                "Crypto encryption failed for '%s': %s", secret_key, e,
            )

            if self._fallback_to_plaintext:
                async with self._lock:
                    self._stats["fallback_count"] += 1

                try:
                    item = await self._secrets.set(
                        key=secret_key,
                        value=value,
                        namespace=namespace,
                    )

                    duration_ms = (time.perf_counter() - start) * 1000
                    async with self._lock:
                        self._stats["total_duration_ms"] += duration_ms

                    logger.warning(
                        "Stored plaintext fallback for '%s' "
                        "in namespace '%s'",
                        secret_key, namespace,
                    )

                    return {
                        "success": True,
                        "secret_key": secret_key,
                        "namespace": namespace,
                        "encrypted": None,
                        "fallback": True,
                        "duration_ms": duration_ms,
                    }
                except Exception as fallback_err:
                    async with self._lock:
                        self._stats["errors"] += 1

                    raise SecretEncryptionError(
                        secret_key,
                        f"Crypto failed: {e}; "
                        f"Fallback also failed: {fallback_err}",
                    )

            async with self._lock:
                self._stats["errors"] += 1

            raise SecretEncryptionError(
                secret_key,
                str(e),
            )

        except Exception as e:
            async with self._lock:
                self._stats["errors"] += 1

            logger.error(
                "Unexpected error encrypting secret '%s': %s",
                secret_key, e,
            )
            raise SecretEncryptionError(secret_key, str(e))

    async def decrypt_secret(
        self,
        secret_key: str,
        namespace: str = "default",
    ) -> str:
        """
        Read an encrypted secret and decrypt it.

        Retrieves the encrypted payload from SecretsManager,
        deserializes it to an EncryptionResult, and decrypts
        using CryptoService.

        If the stored value is plaintext (fallback scenario),
        returns it directly.

        Args:
            secret_key: The secret key to decrypt.
            namespace: The secrets namespace.

        Returns:
            The decrypted plaintext value.

        Raises:
            SecretNotFoundError: If the secret is not found.
            SecretEncryptionError: If decryption fails.
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["decrypt_operations"] += 1

        try:
            stored_value = await self._secrets.get(
                key=secret_key,
                namespace=namespace,
            )
        except SecretNotFoundError:
            async with self._lock:
                self._stats["errors"] += 1
            raise
        except Exception as e:
            async with self._lock:
                self._stats["errors"] += 1
            raise SecretEncryptionError(
                secret_key,
                f"Failed to read secret: {e}",
            )

        if stored_value is None:
            async with self._lock:
                self._stats["errors"] += 1
            raise SecretNotFoundError(secret_key, namespace)

        try:
            payload = json.loads(stored_value)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Secret '%s' in namespace '%s' is not a valid "
                "encrypted payload, returning as plaintext",
                secret_key, namespace,
            )
            return stored_value

        if not isinstance(payload, dict):
            logger.warning(
                "Secret '%s' has unexpected format, "
                "returning as plaintext",
                secret_key,
            )
            return stored_value

        if "_integration" not in payload:
            logger.info(
                "Secret '%s' is a plaintext JSON value, "
                "returning as-is",
                secret_key,
            )
            return stored_value

        encryption_result = EncryptionResult(
            ciphertext=payload.get("ciphertext", ""),
            algorithm=payload.get("algorithm", ""),
            key_id=payload.get("key_id", ""),
            encrypted_dek=payload.get("encrypted_dek", ""),
            nonce=payload.get("nonce", ""),
            aad=payload.get("aad", ""),
            metadata=payload.get("metadata", {}),
        )

        try:
            decryption_result = await self._crypto.decrypt(
                encrypted=encryption_result,
            )

            duration_ms = (time.perf_counter() - start) * 1000
            async with self._lock:
                self._stats["total_duration_ms"] += duration_ms

            plaintext = decryption_result.plaintext.decode("utf-8")
            logger.debug(
                "Decrypted secret '%s' from namespace '%s'",
                secret_key, namespace,
            )
            return plaintext

        except (CryptoDecryptionError, RuntimeError) as e:
            async with self._lock:
                self._stats["errors"] += 1

            logger.error(
                "Crypto decryption failed for '%s': %s", secret_key, e,
            )
            raise SecretEncryptionError(
                secret_key,
                f"Decryption failed: {e}",
            )

        except Exception as e:
            async with self._lock:
                self._stats["errors"] += 1

            logger.error(
                "Unexpected error decrypting secret '%s': %s",
                secret_key, e,
            )
            raise SecretEncryptionError(secret_key, str(e))

    async def rotate_secret(
        self,
        secret_key: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Rotate an encrypted secret with crypto key rotation.

        Reads the encrypted secret, decrypts it, re-encrypts
        with the current crypto key (which may have been rotated),
        and stores the new encrypted payload.

        Args:
            secret_key: The secret key to rotate.
            namespace: The secrets namespace.

        Returns:
            Dict with rotation result:
                - success: Whether rotation succeeded
                - secret_key: The rotated secret key
                - namespace: The namespace used
                - duration_ms: Operation duration
                - error: Error message if failed

        Raises:
            SecretEncryptionError: If rotation fails.
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["rotate_operations"] += 1

        try:
            plaintext = await self.decrypt_secret(
                secret_key=secret_key,
                namespace=namespace,
            )

            result = await self.encrypt_secret(
                secret_key=secret_key,
                value=plaintext,
                namespace=namespace,
            )

            duration_ms = (time.perf_counter() - start) * 1000

            logger.info(
                "Rotated encrypted secret '%s' "
                "in namespace '%s'",
                secret_key, namespace,
            )

            return {
                "success": True,
                "secret_key": secret_key,
                "namespace": namespace,
                "duration_ms": duration_ms,
                "fallback": result.get("fallback", False),
            }

        except Exception as e:
            async with self._lock:
                self._stats["errors"] += 1

            duration_ms = (time.perf_counter() - start) * 1000

            logger.error(
                "Failed to rotate encrypted secret '%s': %s",
                secret_key, e,
            )

            return {
                "success": False,
                "secret_key": secret_key,
                "namespace": namespace,
                "duration_ms": duration_ms,
                "error": str(e),
            }

    async def batch_encrypt(
        self,
        secrets_dict: Dict[str, str],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Batch encrypt multiple secrets.

        Encrypts each secret in the dictionary and stores
        all encrypted payloads in the specified namespace.

        Args:
            secrets_dict: Dict mapping secret keys to values.
            namespace: The secrets namespace.

        Returns:
            Dict with batch results:
                - total: Total number of secrets processed
                - succeeded: List of successfully encrypted keys
                - failed: Dict of failed keys with error messages
                - fallback: List of keys using plaintext fallback
                - duration_ms: Total operation duration
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["batch_encrypt_operations"] += 1

        succeeded: List[str] = []
        failed: Dict[str, str] = {}
        fallback: List[str] = []

        for secret_key, value in secrets_dict.items():
            try:
                result = await self.encrypt_secret(
                    secret_key=secret_key,
                    value=value,
                    namespace=namespace,
                )
                if result.get("fallback"):
                    fallback.append(secret_key)
                else:
                    succeeded.append(secret_key)
            except Exception as e:
                failed[secret_key] = str(e)

        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Batch encrypted %d secrets in namespace '%s' "
            "(succeeded=%d, failed=%d, fallback=%d)",
            len(secrets_dict),
            namespace,
            len(succeeded),
            len(failed),
            len(fallback),
        )

        return {
            "total": len(secrets_dict),
            "succeeded": succeeded,
            "failed": failed,
            "fallback": fallback,
            "duration_ms": duration_ms,
        }

    async def batch_decrypt(
        self,
        keys_list: List[str],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Batch decrypt multiple secrets.

        Reads and decrypts each secret key in the list
        from the specified namespace.

        Args:
            keys_list: List of secret keys to decrypt.
            namespace: The secrets namespace.

        Returns:
            Dict with batch results:
                - total: Total number of secrets processed
                - values: Dict of decrypted key-value pairs
                - failed: Dict of failed keys with error messages
                - duration_ms: Total operation duration
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["batch_decrypt_operations"] += 1

        values: Dict[str, str] = {}
        failed: Dict[str, str] = {}

        for secret_key in keys_list:
            try:
                value = await self.decrypt_secret(
                    secret_key=secret_key,
                    namespace=namespace,
                )
                values[secret_key] = value
            except Exception as e:
                failed[secret_key] = str(e)

        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Batch decrypted %d secrets in namespace '%s' "
            "(succeeded=%d, failed=%d)",
            len(keys_list),
            namespace,
            len(values),
            len(failed),
        )

        return {
            "total": len(keys_list),
            "values": values,
            "failed": failed,
            "duration_ms": duration_ms,
        }

    async def verify_integrity(
        self,
        secret_key: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Verify encrypted secret integrity.

        Performs a round-trip decryption test to verify
        the encrypted secret can be successfully decrypted.
        Also validates the encrypted payload structure
        and checks the crypto service integrity.

        Args:
            secret_key: The secret key to verify.
            namespace: The secrets namespace.

        Returns:
            Dict with verification result:
                - valid: Whether the secret integrity is intact
                - secret_key: The verified secret key
                - namespace: The namespace used
                - structure_valid: Whether encrypted payload
                    structure is valid
                - decryption_ok: Whether decryption succeeds
                - crypto_integrity: Crypto service integrity check
                - errors: List of integrity errors
                - duration_ms: Operation duration
        """
        start = time.perf_counter()
        async with self._lock:
            self._stats["verify_operations"] += 1

        errors: List[str] = []
        structure_valid = True
        decryption_ok = False
        crypto_integrity: Dict[str, Any] = {}

        try:
            stored_value = await self._secrets.get(
                key=secret_key,
                namespace=namespace,
            )
        except SecretNotFoundError as e:
            errors.append(f"Secret not found: {e}")
            duration_ms = (time.perf_counter() - start) * 1000
            return {
                "valid": False,
                "secret_key": secret_key,
                "namespace": namespace,
                "structure_valid": False,
                "decryption_ok": False,
                "crypto_integrity": {},
                "errors": errors,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            errors.append(f"Failed to read secret: {e}")
            duration_ms = (time.perf_counter() - start) * 1000
            return {
                "valid": False,
                "secret_key": secret_key,
                "namespace": namespace,
                "structure_valid": False,
                "decryption_ok": False,
                "crypto_integrity": {},
                "errors": errors,
                "duration_ms": duration_ms,
            }

        if stored_value is None:
            errors.append("Secret value is None")
            duration_ms = (time.perf_counter() - start) * 1000
            return {
                "valid": False,
                "secret_key": secret_key,
                "namespace": namespace,
                "structure_valid": False,
                "decryption_ok": False,
                "crypto_integrity": {},
                "errors": errors,
                "duration_ms": duration_ms,
            }

        try:
            payload = json.loads(stored_value)

            if not isinstance(payload, dict):
                structure_valid = False
                errors.append("Payload is not a dictionary")
            elif "_integration" not in payload:
                structure_valid = True
                decryption_ok = True
            else:
                required_fields = [
                    "ciphertext",
                    "algorithm",
                    "key_id",
                    "encrypted_dek",
                    "nonce",
                ]
                for field in required_fields:
                    if field not in payload:
                        structure_valid = False
                        errors.append(
                            f"Missing required field: {field}"
                        )

                if structure_valid:
                    try:
                        encryption_result = EncryptionResult(
                            ciphertext=payload.get("ciphertext", ""),
                            algorithm=payload.get("algorithm", ""),
                            key_id=payload.get("key_id", ""),
                            encrypted_dek=payload.get(
                                "encrypted_dek", ""
                            ),
                            nonce=payload.get("nonce", ""),
                            aad=payload.get("aad", ""),
                            metadata=payload.get("metadata", {}),
                        )

                        decryption_result = await self._crypto.decrypt(
                            encrypted=encryption_result,
                        )
                        decryption_ok = True

                    except Exception as e:
                        decryption_ok = False
                        errors.append(
                            f"Decryption failed: {e}"
                        )

        except (json.JSONDecodeError, TypeError) as e:
            structure_valid = False
            errors.append(f"Invalid JSON payload: {e}")

        try:
            integrity_check = self._crypto.get_integrity()
            integrity_result = integrity_check.verify()
            crypto_integrity = integrity_result.to_dict()
        except Exception as e:
            crypto_integrity = {"error": str(e)}
            errors.append(f"Crypto integrity check failed: {e}")

        valid = (
            structure_valid
            and decryption_ok
            and crypto_integrity.get("valid", True)
        )

        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Verified integrity of secret '%s' "
            "in namespace '%s': valid=%s",
            secret_key, namespace, valid,
        )

        return {
            "valid": valid,
            "secret_key": secret_key,
            "namespace": namespace,
            "structure_valid": structure_valid,
            "decryption_ok": decryption_ok,
            "crypto_integrity": crypto_integrity,
            "errors": errors,
            "duration_ms": duration_ms,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get integration statistics.

        Returns operation counts and timing
        information for monitoring and
        observability.

        Returns:
            Dict with statistics:
                - encrypt_operations: Total encrypt calls
                - decrypt_operations: Total decrypt calls
                - rotate_operations: Total rotate calls
                - batch_encrypt_operations: Total batch
                    encrypt calls
                - batch_decrypt_operations: Total batch
                    decrypt calls
                - verify_operations: Total verify calls
                - fallback_count: Number of plaintext fallbacks
                - errors: Total error count
                - total_duration_ms: Cumulative operation
                    duration in milliseconds
                - crypto_stats: Underlying crypto service stats
        """
        stats = dict(self._stats)

        try:
            crypto_stats = self._crypto.get_stats()
            stats["crypto_stats"] = crypto_stats
        except Exception:
            stats["crypto_stats"] = None

        return stats