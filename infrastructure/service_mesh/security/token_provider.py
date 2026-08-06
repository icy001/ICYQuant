"""Token provider for ICYQuant Service Mesh.

Provides ``TokenProvider`` for JWT (reserved), OAuth (reserved),
and internal mesh token generation and validation.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .exceptions import TokenError

logger = logging.getLogger(__name__)


class TokenRecord:
    """A token record."""

    def __init__(
        self,
        token: str,
        principal: str,
        token_type: str = "mesh",
        ttl_seconds: int = 3600,
        claims: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.token = token
        self.principal = principal
        self.token_type = token_type
        self.ttl_seconds = ttl_seconds
        self.claims = claims or {}
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token[:8] + "...",
            "principal": self.principal,
            "token_type": self.token_type,
            "ttl_seconds": self.ttl_seconds,
            "claims": self.claims,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
            "is_valid": self.is_valid,
        }


class TokenProvider:
    """Provides authentication tokens."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tokens: Dict[str, TokenRecord] = {}
        self._issue_count = 0
        self._validation_count = 0

    def issue_token(
        self,
        principal: str,
        token_type: str = "mesh",
        ttl_seconds: int = 3600,
        claims: Optional[Dict[str, Any]] = None,
    ) -> TokenRecord:
        """Issue a new token."""
        raw = f"{principal}:{time.time()}:{self._issue_count}"
        token = hashlib.sha256(raw.encode()).hexdigest()
        record = TokenRecord(
            token=token,
            principal=principal,
            token_type=token_type,
            ttl_seconds=ttl_seconds,
            claims=claims or {},
        )
        with self._lock:
            self._tokens[token] = record
            self._issue_count += 1
        logger.info("Token issued for: %s", principal)
        return record

    def validate_token(self, token: str) -> bool:
        """Validate a token."""
        with self._lock:
            record = self._tokens.get(token)
            self._validation_count += 1
        if not record:
            return False
        return record.is_valid

    def get_token(self, token: str) -> Optional[TokenRecord]:
        with self._lock:
            return self._tokens.get(token)

    def revoke_token(self, token: str) -> bool:
        with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                return True
            return False

    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [t for t, r in self._tokens.items() if r.is_expired]
            for t in expired:
                del self._tokens[t]
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_tokens": len(self._tokens),
                "active_tokens": sum(1 for r in self._tokens.values() if r.is_valid),
                "issue_count": self._issue_count,
                "validation_count": self._validation_count,
            }
