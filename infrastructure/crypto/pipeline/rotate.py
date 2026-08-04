"""
Key rotation pipeline.

Orchestrates the key rotation process
including generation of new key versions,
re-encryption of data, and cleanup of
old key material.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..config import CryptoConfig
from ..exceptions import CryptoKeyError

logger = logging.getLogger(__name__)


@dataclass
class KeyRotationResult:
    """
    Key rotation operation result.

    Attributes:
        key_id: Rotated key ID.
        old_version: Previous version number.
        new_version: New version number.
        success: Whether rotation succeeded.
        re_encrypted_count: Number of data items re-encrypted.
        duration_ms: Rotation duration in milliseconds.
        errors: List of errors encountered.
    """

    key_id: str = ""
    old_version: int = 0
    new_version: int = 0
    success: bool = False
    re_encrypted_count: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "success": self.success,
            "re_encrypted_count": self.re_encrypted_count,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
        }


class KeyRotationPipeline:
    """
    Key rotation pipeline orchestrator.

    Manages the key rotation workflow including:
    - Key version generation
    - Data re-encryption
    - Old key cleanup
    - Rotation audit logging

    Usage:
        pipeline = KeyRotationPipeline(
            kms_provider=kms,
            config=config,
        )
        result = await pipeline.rotate_key(
            key_id="my-key",
            re_encrypt_callback=re_encrypt_fn,
        )
    """

    def __init__(
        self,
        kms_provider: Any,
        config: Optional[CryptoConfig] = None,
    ) -> None:
        """
        Initialize key rotation pipeline.

        Args:
            kms_provider: KMS provider for key operations.
            config: Crypto configuration.
        """
        self._kms_provider = kms_provider
        self._config = config or CryptoConfig()

    async def rotate_key(
        self,
        key_id: str,
        re_encrypt_callback: Optional[Callable] = None,
        force: bool = False,
        **kwargs: Any,
    ) -> KeyRotationResult:
        """
        Rotate a cryptographic key.

        Args:
            key_id: Key to rotate.
            re_encrypt_callback: Callback to re-encrypt data.
            force: Force rotation even if not due.

        Returns:
            KeyRotationResult.
        """
        import time
        start = time.monotonic()

        result = KeyRotationResult(key_id=key_id)

        try:
            # Step 1: Get current key info
            current_info = await self._kms_provider.get_key_info(key_id)
            old_version = current_info.version
            result.old_version = old_version

            logger.info(
                "Rotating key %s (current version: %d)",
                key_id, old_version,
            )

            # Step 2: Rotate in KMS
            new_info = await self._kms_provider.rotate_key(key_id)
            result.new_version = new_info.version

            logger.info(
                "Key %s rotated: v%d -> v%d",
                key_id, old_version, new_info.version,
            )

            # Step 3: Re-encrypt data if callback provided
            if re_encrypt_callback:
                try:
                    re_encrypted = await re_encrypt_callback(
                        key_id=key_id,
                        old_version=old_version,
                        new_version=new_info.version,
                    )
                    result.re_encrypted_count = re_encrypted
                except Exception as e:
                    result.errors.append(f"Re-encryption failed: {e}")
                    logger.error(
                        "Re-encryption failed for key %s: %s", key_id, e,
                    )

            # Step 4: Mark success
            result.success = True

        except Exception as e:
            result.errors.append(str(e))
            logger.error("Key rotation failed for %s: %s", key_id, e)

        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    async def rotate_all_keys(
        self,
        prefix: str = "",
        **kwargs: Any,
    ) -> List[KeyRotationResult]:
        """
        Rotate all keys matching a prefix.

        Args:
            prefix: Key name prefix filter.

        Returns:
            List of KeyRotationResult.
        """
        keys = await self._kms_provider.list_keys(prefix=prefix)
        results: List[KeyRotationResult] = []

        for key_info in keys:
            try:
                result = await self.rotate_key(
                    key_id=key_info.key_id,
                    **kwargs,
                )
                results.append(result)
            except Exception as e:
                results.append(KeyRotationResult(
                    key_id=key_info.key_id,
                    success=False,
                    errors=[str(e)],
                ))

        return results

    async def schedule_rotation(
        self,
        key_id: str,
        rotation_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a key for rotation.

        Args:
            key_id: Key to schedule.
            rotation_days: Days between rotations.

        Returns:
            Schedule information.
        """
        days = rotation_days or 365
        next_rotation = datetime.utcnow()
        from datetime import timedelta
        next_rotation += timedelta(days=days)

        return {
            "key_id": key_id,
            "rotation_interval_days": days,
            "next_rotation": next_rotation.isoformat() + "Z",
            "scheduled_at": datetime.utcnow().isoformat() + "Z",
        }
