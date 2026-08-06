"""mTLS engine for ICYQuant Service Mesh.

Provides ``MTLSEngine`` for mutual TLS authentication, automatic
handshake, and encrypted channel management between mesh services.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .certificate_manager import CertificateManager
from .handshake import HandshakeManager, HandshakeSession, HandshakeState

logger = logging.getLogger(__name__)


class MTLSSession:
    """An active mTLS session."""

    def __init__(
        self,
        session_id: str,
        client_identity: str,
        server_identity: str,
        handshake: HandshakeSession,
    ) -> None:
        self.session_id = session_id
        self.client_identity = client_identity
        self.server_identity = server_identity
        self.handshake = handshake
        self.established_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.bytes_sent = 0
        self.bytes_received = 0
        self._active = True

    @property
    def is_active(self) -> bool:
        return self._active

    def record_activity(self, sent: int = 0, received: int = 0) -> None:
        self.bytes_sent += sent
        self.bytes_received += received
        self.last_activity = datetime.utcnow()

    def close(self) -> None:
        self._active = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "client_identity": self.client_identity,
            "server_identity": self.server_identity,
            "established_at": self.established_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "active": self.is_active,
        }


class MTLSEngine:
    """mTLS engine for secure service-to-service communication."""

    def __init__(
        self,
        cert_manager: Optional[CertificateManager] = None,
        handshake_manager: Optional[HandshakeManager] = None,
    ) -> None:
        self._cert_manager = cert_manager or CertificateManager()
        self._handshake_manager = handshake_manager or HandshakeManager()
        self._lock = threading.RLock()
        self._sessions: Dict[str, MTLSSession] = {}
        self._handshake_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._started = False

    async def establish(
        self,
        client_identity: str,
        server_identity: str,
        client_cert=None,
        server_cert=None,
    ) -> Dict[str, Any]:
        """Establish a mutual TLS connection."""
        with self._lock:
            self._handshake_count += 1

        handshake = await self._handshake_manager.perform_handshake(
            client_identity=client_identity,
            server_identity=server_identity,
            client_cert=client_cert,
            server_cert=server_cert,
        )

        if handshake.state != HandshakeState.ESTABLISHED:
            with self._lock:
                self._failure_count += 1
            return {
                "success": False,
                "reason": "handshake_failed",
                "errors": handshake.errors,
            }

        session = MTLSSession(
            session_id=handshake.session_id,
            client_identity=client_identity,
            server_identity=server_identity,
            handshake=handshake,
        )

        with self._lock:
            self._sessions[session.session_id] = session
            self._success_count += 1

        logger.info("mTLS session established: %s", session.session_id)
        return {
            "success": True,
            "session_id": session.session_id,
            "client_identity": client_identity,
            "server_identity": server_identity,
            "cipher_suite": handshake.cipher_suite,
        }

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.close()
                return True
            return False

    def get_session(self, session_id: str) -> Optional[MTLSSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_active_sessions(self) -> List[MTLSSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.is_active]

    def record_activity(self, session_id: str, sent: int = 0, received: int = 0) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_active:
                session.record_activity(sent, received)
                return True
            return False

    def start(self) -> None:
        self._cert_manager.start()
        self._started = True

    def stop(self) -> None:
        self._cert_manager.stop()
        with self._lock:
            for session in self._sessions.values():
                session.close()
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def cert_manager(self) -> CertificateManager:
        return self._cert_manager

    @property
    def handshake_manager(self) -> HandshakeManager:
        return self._handshake_manager

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started": self._started,
                "handshake_count": self._handshake_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "active_sessions": sum(1 for s in self._sessions.values() if s.is_active),
                "total_sessions": len(self._sessions),
                "handshake_stats": self._handshake_manager.get_stats(),
            }
