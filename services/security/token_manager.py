"""
ICYQuant Token Manager

JWT/Security token lifecycle management with configurable claims,
validation, and token exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import secrets
import hashlib
import base64
import json

logger = logging.getLogger(__name__)


class TokenStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"


@dataclass
class TokenConfig:
    issuer: str = "icyquant"
    audience: str = "icyquant-services"
    expiration_minutes: int = 60
    refresh_expiration_days: int = 30
    signing_algorithm: str = "HS256"
    include_claims: Set[str] = field(default_factory=lambda: {"sub", "iat", "exp", "iss", "aud", "jti"})
    custom_claims: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "issuer": self.issuer,
            "audience": self.audience,
            "expirationMinutes": self.expiration_minutes,
            "refreshExpirationDays": self.refresh_expiration_days,
            "signingAlgorithm": self.signing_algorithm,
        }


@dataclass
class TokenClaims:
    subject: str = ""
    issuer: str = "icyquant"
    audience: str = "icyquant-services"
    issued_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    jwt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scopes: Set[str] = field(default_factory=set)
    roles: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        result = {
            "sub": self.subject,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": int(self.issued_at.timestamp()),
            "jti": self.jwt_id,
            "scopes": list(self.scopes),
            "roles": self.roles,
        }
        if self.expires_at:
            result["exp"] = int(self.expires_at.timestamp())
        result.update(self.metadata)
        return result


@dataclass
class TokenValidation:
    valid: bool = False
    status: TokenStatus = TokenStatus.INVALID
    claims: Optional[TokenClaims] = None
    errors: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "status": self.status.value,
            "errors": self.errors,
            "claims": self.claims.to_dict() if self.claims else None,
            "validatedAt": self.validated_at.isoformat(),
        }


class TokenManager:
    """
    JWT/Security token lifecycle management.

    Handles token creation, validation, refresh, revocation, and exchange.
    """

    def __init__(self, config: Optional[TokenConfig] = None):
        self._config = config or TokenConfig()
        self._signing_key = secrets.token_bytes(32)
        self._tokens: Dict[str, Dict] = {}
        self._revoked_tokens: Set[str] = set()
        self._refresh_tokens: Dict[str, str] = {}
        self._audit_log: List[Dict] = []
        self._max_audit_size = 10000

    def create_token(
        self,
        subject: str,
        scopes: Optional[Set[str]] = None,
        roles: Optional[List[str]] = None,
        expires_in_minutes: Optional[int] = None,
        custom_claims: Optional[Dict[str, str]] = None,
    ) -> str:
        exp_minutes = expires_in_minutes or self._config.expiration_minutes
        now = datetime.now()
        expires_at = now + timedelta(minutes=exp_minutes)

        claims = TokenClaims(
            subject=subject,
            issuer=self._config.issuer,
            audience=self._config.audience,
            issued_at=now,
            expires_at=expires_at,
            scopes=scopes or set(),
            roles=roles or [],
            metadata=custom_claims or {},
        )

        token_value = self._encode(claims)
        self._tokens[claims.jwt_id] = {
            "claims": claims,
            "revoked": False,
            "created_at": now,
        }

        self._audit("create", subject, claims.jwt_id)
        return token_value

    def create_refresh_token(
        self,
        subject: str,
        access_token_jti: str,
    ) -> str:
        now = datetime.now()
        expires_at = now + timedelta(days=self._config.refresh_expiration_days)

        claims = TokenClaims(
            subject=subject,
            issuer=self._config.issuer,
            audience=self._config.audience,
            issued_at=now,
            expires_at=expires_at,
            scopes={"refresh"},
        )

        token_value = self._encode(claims)
        self._refresh_tokens[claims.jwt_id] = access_token_jti
        self._tokens[claims.jwt_id] = {
            "claims": claims,
            "revoked": False,
            "created_at": now,
        }

        self._audit("create_refresh", subject, claims.jwt_id)
        return token_value

    def validate_token(self, token_value: str) -> TokenValidation:
        errors: List[str] = []
        try:
            claims = self._decode(token_value)
        except Exception as e:
            return TokenValidation(
                valid=False,
                status=TokenStatus.INVALID,
                errors=[str(e)],
            )

        jti = claims.get("jti", "")
        exp = claims.get("exp", 0)
        now = datetime.now().timestamp()

        if jti in self._revoked_tokens:
            return TokenValidation(
                valid=False,
                status=TokenStatus.REVOKED,
                claims=self._claims_from_dict(claims),
                errors=["Token has been revoked"],
            )

        if exp and now > exp:
            return TokenValidation(
                valid=False,
                status=TokenStatus.EXPIRED,
                claims=self._claims_from_dict(claims),
                errors=["Token has expired"],
            )

        validation = TokenValidation(
            valid=True,
            status=TokenStatus.ACTIVE,
            claims=self._claims_from_dict(claims),
            errors=errors,
        )
        self._audit("validate", claims.get("sub", ""), jti)
        return validation

    def refresh_access_token(self, refresh_token_value: str) -> Optional[str]:
        validation = self.validate_token(refresh_token_value)
        if not validation.valid or not validation.claims:
            return None

        if "refresh" not in validation.claims.scopes:
            return None

        subject = validation.claims.subject
        original_jti = self._refresh_tokens.get(validation.claims.jwt_id)
        if original_jti:
            self.revoke_token(original_jti)

        return self.create_token(
            subject=subject,
            scopes=validation.claims.scopes - {"refresh"},
            roles=validation.claims.roles,
        )

    def revoke_token(self, jti: str):
        self._revoked_tokens.add(jti)
        if jti in self._tokens:
            self._tokens[jti]["revoked"] = True
            self._audit("revoke", self._tokens[jti]["claims"].get("sub", ""), jti)

    def revoke_all_user_tokens(self, subject: str):
        for jti, data in self._tokens.items():
            if data["claims"].get("sub") == subject:
                self.revoke_token(jti)

    def exchange_token(
        self,
        token_value: str,
        new_audience: str,
        new_scopes: Optional[Set[str]] = None,
    ) -> Optional[str]:
        validation = self.validate_token(token_value)
        if not validation.valid or not validation.claims:
            return None

        new_claims = TokenClaims(
            subject=validation.claims.subject,
            issuer=self._config.issuer,
            audience=new_audience,
            scopes=new_scopes or validation.claims.scopes,
            roles=validation.claims.roles,
        )
        return self._encode(new_claims)

    def update_config(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def get_config(self) -> TokenConfig:
        return self._config

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        return self._audit_log[-limit:]

    def to_dict(self) -> Dict:
        return {
            "config": self._config.to_dict(),
            "activeTokens": sum(1 for t in self._tokens.values() if not t["revoked"]),
            "revokedCount": len(self._revoked_tokens),
        }

    def _encode(self, claims: TokenClaims) -> str:
        payload = claims.to_dict()
        payload_bytes = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")

        signing_input = f"{self._config.issuer}.{payload_b64}"
        signature = hashlib.sha256(
            signing_input.encode() + self._signing_key
        ).hexdigest()

        return f"{self._config.issuer}.{payload_b64}.{signature}"

    def _decode(self, token_value: str) -> Dict:
        parts = token_value.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        issuer, payload_b64, signature = parts
        expected_sig = hashlib.sha256(
            f"{issuer}.{payload_b64}".encode() + self._signing_key
        ).hexdigest()
        if signature != expected_sig:
            raise ValueError("Invalid token signature")

        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)

    def _claims_from_dict(self, data: Dict) -> TokenClaims:
        return TokenClaims(
            subject=data.get("sub", ""),
            issuer=data.get("iss", ""),
            audience=data.get("aud", ""),
            issued_at=datetime.fromtimestamp(data.get("iat", 0)),
            expires_at=datetime.fromtimestamp(data["exp"]) if "exp" in data else None,
            jwt_id=data.get("jti", ""),
            scopes=set(data.get("scopes", [])),
            roles=data.get("roles", []),
            metadata={k: v for k, v in data.items()
                     if k not in ("sub", "iss", "aud", "iat", "exp", "jti", "scopes", "roles")},
        )

    def _audit(self, action: str, subject: str, jti: str):
        self._audit_log.append({
            "action": action,
            "subject": subject,
            "jti": jti,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._audit_log) > self._max_audit_size:
            self._audit_log = self._audit_log[-self._max_audit_size:]
