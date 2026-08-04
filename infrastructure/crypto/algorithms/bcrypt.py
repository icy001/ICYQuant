"""
Bcrypt password hashing.

Implements bcrypt password hashing
with configurable work factor
for secure password storage.
"""

from __future__ import annotations

from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoHashError
from ..registry import PasswordHashAlgorithm

try:
    import bcrypt as _bcrypt
    _HAS_BCRYPT = True
except ImportError:
    try:
        from passlib.hash import bcrypt as _bcrypt
        _HAS_BCRYPT = True
    except ImportError:
        _HAS_BCRYPT = False


class BcryptPassword(PasswordHashAlgorithm):
    """
    Bcrypt password hashing.

    Provides adaptive password hashing
    with configurable work factor,
    designed to resist brute-force
    attacks via intentional slowness.

    Features:
    - Adaptive work factor (default: 12)
    - Built-in salt generation
    - One-way hashing
    - Resists GPU/ASIC attacks
    """

    name: str = AlgorithmName.BCRYPT.value
    version: str = "1.0.0"

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    async def hash_password(
        self,
        password: str,
        **kwargs: Any,
    ) -> str:
        """
        Hash a password with bcrypt.

        Args:
            password: Plaintext password.
            **kwargs:
                rounds: Override default work factor.

        Returns:
            Bcrypt hash string.
        """
        if not _HAS_BCRYPT:
            raise CryptoHashError(
                "bcrypt library not available",
            )

        try:
            rounds = kwargs.get("rounds", self._rounds)
            if hasattr(_bcrypt, "hashpw"):
                # passlib-style API
                return _bcrypt.hash(
                    password,
                    rounds=rounds,
                )
            else:
                # py-bcrypt style API
                return _bcrypt.hashpw(
                    password.encode("utf-8"),
                    _bcrypt.gensalt(rounds=rounds),
                ).decode("utf-8")
        except Exception as e:
            raise CryptoHashError(f"Bcrypt hashing failed: {e}")

    async def verify_password(
        self,
        password: str,
        hash_value: str,
        **kwargs: Any,
    ) -> bool:
        """
        Verify a password against its bcrypt hash.

        Args:
            password: Plaintext password.
            hash_value: Stored bcrypt hash.

        Returns:
            True if password matches.
        """
        if not _HAS_BCRYPT:
            return False

        try:
            if hasattr(_bcrypt, "verify"):
                # passlib-style API
                return _bcrypt.verify(password, hash_value)
            else:
                # py-bcrypt style API
                return _bcrypt.checkpw(
                    password.encode("utf-8"),
                    hash_value.encode("utf-8"),
                )
        except Exception:
            return False

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "rounds": self._rounds,
            "algorithm": "bcrypt",
        }
