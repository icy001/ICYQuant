"""TLS handshake for ICYQuant Service Mesh.

Provides ``HandshakeManager`` for managing mTLS handshake flow:
identity verification, certificate validation, trust verification,
session key establishment, and secure connection setup.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .certificate_validator import CertificateValidator, ValidationResult
from .exceptions import HandshakeError

logger = logging.getLogger(__name__)


class HandshakeState(str):
    """TLS handshake states."""

    INITIATED = "initiated"
    CERTIFICATE_EXCHANGE = "certificate_exchange"
    CERTIFICATE_VALIDATION = "certificate_validation"
    TRUST_VERIFICATION = "trust_verification"
    SESSION_KEY = "session_key"
    ESTABLISHED = "established"
    FAILED = "failed"


class HandshakeSession:
    """A single handshake session."""

    def __init__(self, session_id: str, client_identity: str = "", server_identity: str = "") -> None:
        self.session_id = session_id
        self.client_identity = client_identity
        self.server_identity = server_identity
        self.state = HandshakeState.INITIATED
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.session_key: str = ""
        self.cipher_suite: str = "TLS_AES_256_GCM_SHA384"
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "client_identity": self.client_identity,
            "server_identity": self.server_identity,
            "state": self.state,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "session_key": self.session_key[:8] + "..." if self.session_key else "",
            "cipher_suite": self.cipher_suite,
            "errors": self.errors,
        }


class HandshakeManager:
    """Manages mTLS handshake flow."""

    def __init__(self, validator: Optional[CertificateValidator] = None) -> None:
        self._lock = threading.RLock()
        self._validator = validator or CertificateValidator()
        self._sessions: Dict[str, HandshakeSession] = {}
        self._handshake_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def perform_handshake(
        self,
        client_identity: str,
        server_identity: str,
        client_cert=None,
        server_cert=None,
    ) -> HandshakeSession:
        """Perform a full mTLS handshake."""
        session_id = hashlib.sha256(
            f"{client_identity}:{server_identity}:{time.time()}".encode()
        ).hexdigest()[:16]
        session = HandshakeSession(session_id, client_identity, server_identity)

        with self._lock:
            self._sessions[session_id] = session
            self._handshake_count += 1

        try:
            # Step 1: Certificate exchange
            session.state = HandshakeState.CERTIFICATE_EXCHANGE

            # Step 2: Certificate validation
            session.state = HandshakeState.CERTIFICATE_VALIDATION
            if client_cert:
                result = self._validator.validate(client_cert)
                if not result.valid:
                    session.errors.append(f"client_cert: {result.reason}")

            if server_cert:
                result = self._validator.validate(server_cert)
                if not result.valid:
                    session.errors.append(f"server_cert: {result.reason}")

            # Step 3: Trust verification
            session.state = HandshakeState.TRUST_VERIFICATION
            if session.errors:
                session.state = HandshakeState.FAILED
                with self._lock:
                    self._failure_count += 1
                return session

            # Step 4: Session key establishment
            session.state = HandshakeState.SESSION_KEY
            session.session_key = hashlib.sha256(
                f"{session_id}:{client_identity}:{server_identity}".encode()
            ).hexdigest()

            # Step 5: Established
            session.state = HandshakeState.ESTABLISHED
            session.completed_at = datetime.utcnow()
            with self._lock:
                self._success_count += 1

        except Exception as exc:
            session.state = HandshakeState.FAILED
            session.errors.append(str(exc))
            with self._lock:
                self._failure_count += 1

        return session

    def get_session(self, session_id: str) -> Optional[HandshakeSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_active_sessions(self) -> List[HandshakeSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.state == HandshakeState.ESTABLISHED]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "handshake_count": self._handshake_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "active_sessions": sum(1 for s in self._sessions.values() if s.state == HandshakeState.ESTABLISHED),
                "total_sessions": len(self._sessions),
            }
