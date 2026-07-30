"""
ICYQuant Authentication Service

Handles multi-provider authentication: OAuth2, OIDC, SAML, JWT, MFA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import hashlib
import secrets

logger = logging.getLogger(__name__)


class AuthProvider(str, Enum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    SAML = "saml"
    JWT = "jwt"
    API_KEY = "api_key"
    MFA = "mfa"


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    ID = "id"
    SERVICE = "service"
    API = "api"


class MFAProvider(str, Enum):
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"
    HARDWARE_KEY = "hardware_key"


class AuthenticationError(Exception):
    pass


@dataclass
class Token:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    token_type: TokenType = TokenType.ACCESS
    token_value: str = ""
    issued_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    revoked: bool = False
    metadata: Dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired()

    def revoke(self):
        self.revoked = True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "type": self.token_type.value,
            "issuedAt": self.issued_at.isoformat(),
            "expiresAt": self.expires_at.isoformat(),
            "revoked": self.revoked,
        }


@dataclass
class MFAChallenge:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    provider: MFAProvider = MFAProvider.TOTP
    code: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    verified: bool = False

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tokens: List[Token] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    ip_address: str = ""
    user_agent: str = ""
    mfa_verified: bool = False

    def is_active(self, timeout_minutes: int = 30) -> bool:
        delta = datetime.now() - self.last_activity
        return delta.total_seconds() < timeout_minutes * 60


@dataclass
class UserIdentity:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    provider: AuthProvider = AuthProvider.JWT
    mfa_enabled: bool = False
    mfa_providers: List[MFAProvider] = field(default_factory=list)
    active: bool = True
    last_login: Optional[datetime] = None
    login_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "provider": self.provider.value,
            "mfaEnabled": self.mfa_enabled,
            "active": self.active,
            "lastLogin": self.last_login.isoformat() if self.last_login else None,
            "loginCount": self.login_count,
        }


class AuthenticationService:
    """
    Multi-provider authentication service.

    Supports OAuth2, OIDC, SAML, JWT, API Key, and MFA.
    Manages sessions, tokens, and authentication challenges.
    """

    def __init__(self):
        self._users: Dict[str, UserIdentity] = {}
        self._passwords: Dict[str, str] = {}
        self._sessions: Dict[str, Session] = {}
        self._tokens: Dict[str, Token] = {}
        self._mfa_challenges: Dict[str, MFAChallenge] = {}
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._max_failed_attempts = 5
        self._lockout_duration_minutes = 15

    def register_user(
        self,
        username: str,
        email: str,
        provider: AuthProvider = AuthProvider.JWT,
        mfa_enabled: bool = False,
        password: Optional[str] = None,
    ) -> UserIdentity:
        if username in self._users:
            raise AuthenticationError(f"User {username} already exists")
        user = UserIdentity(
            username=username,
            email=email,
            provider=provider,
            mfa_enabled=mfa_enabled,
            mfa_providers=[MFAProvider.TOTP] if mfa_enabled else [],
        )
        self._users[username] = user
        if password:
            self._passwords[username] = hashlib.sha256(password.encode()).hexdigest()
        logger.info(f"User registered: {username} via {provider.value}")
        return user

    def authenticate(
        self,
        username: str,
        password: str,
        provider: Optional[AuthProvider] = None,
        mfa_code: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Session:
        user = self._users.get(username)
        if not user or not user.active:
            raise AuthenticationError("Invalid credentials")

        self._check_rate_limit(username)

        stored_hash = self._passwords.get(username)
        if stored_hash and stored_hash != hashlib.sha256(password.encode()).hexdigest():
            attempts = self._failed_attempts.setdefault(username, [])
            attempts.append(datetime.now())
            raise AuthenticationError("Invalid credentials")

        if provider and user.provider != provider:
            raise AuthenticationError(f"Provider {provider.value} not configured for user")

        user.last_login = datetime.now()
        user.login_count += 1

        session = Session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = self._create_token(user.id, TokenType.ACCESS)
        refresh_token = self._create_token(user.id, TokenType.REFRESH, expires_hours=720)
        session.tokens.extend([access_token, refresh_token])

        if user.mfa_enabled:
            if not mfa_code:
                self._mfa_challenges[user.id] = MFAChallenge(
                    user_id=user.id,
                    code=secrets.randbelow(1000000),
                )
                raise AuthenticationError("MFA verification required")
            self._verify_mfa(user.id, mfa_code)
            session.mfa_verified = True

        self._sessions[session.id] = session
        logger.info(f"User authenticated: {username}, session: {session.id}")
        return session

    def create_service_token(
        self,
        service_name: str,
        scopes: Optional[Set[str]] = None,
        expires_hours: int = 24,
    ) -> Token:
        token = self._create_token(
            f"service:{service_name}",
            TokenType.SERVICE,
            scopes=scopes,
            expires_hours=expires_hours,
        )
        self._tokens[token.id] = token
        return token

    def validate_token(self, token_value: str) -> Optional[Token]:
        for token in self._tokens.values():
            if token.token_value == token_value and token.is_valid():
                return token
        return None

    def refresh_token(self, refresh_token_value: str) -> Token:
        token = self.validate_token(refresh_token_value)
        if not token or token.token_type != TokenType.REFRESH:
            raise AuthenticationError("Invalid refresh token")
        new_token = self._create_token(token.user_id, TokenType.ACCESS)
        return new_token

    def revoke_token(self, token_id: str):
        if token_id in self._tokens:
            self._tokens[token_id].revoke()

    def revoke_all_user_tokens(self, user_id: str):
        for token in self._tokens.values():
            if token.user_id == user_id:
                token.revoke()

    def end_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            for token in session.tokens:
                self.revoke_token(token.id)

    def get_user(self, username: str) -> Optional[UserIdentity]:
        return self._users.get(username)

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def list_users(self) -> List[UserIdentity]:
        return list(self._users.values())

    def to_dict(self) -> Dict:
        return {
            "users": [u.to_dict() for u in self._users.values()],
            "activeSessions": len(self._sessions),
            "activeTokens": sum(1 for t in self._tokens.values() if t.is_valid()),
        }

    def _create_token(
        self,
        user_id: str,
        token_type: TokenType,
        scopes: Optional[Set[str]] = None,
        expires_hours: int = 1,
    ) -> Token:
        token = Token(
            user_id=user_id,
            token_type=token_type,
            token_value=secrets.token_urlsafe(32),
            expires_at=datetime.now() + timedelta(hours=expires_hours),
            metadata={"scopes": list(scopes) if scopes else []},
        )
        self._tokens[token.id] = token
        return token

    def _check_rate_limit(self, username: str):
        now = datetime.now()
        attempts = self._failed_attempts.get(username, [])
        recent = [a for a in attempts if (now - a).total_seconds() < self._lockout_duration_minutes * 60]
        if len(recent) >= self._max_failed_attempts:
            raise AuthenticationError("Account temporarily locked due to failed attempts")
        self._failed_attempts[username] = recent

    def _verify_mfa(self, user_id: str, code: str):
        challenge = self._mfa_challenges.get(user_id)
        if not challenge or challenge.is_expired():
            raise AuthenticationError("MFA challenge expired")
        if str(challenge.code) != code:
            raise AuthenticationError("Invalid MFA code")
        challenge.verified = True
        del self._mfa_challenges[user_id]
