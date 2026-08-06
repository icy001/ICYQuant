"""Security diagnostics for ICYQuant Service Mesh.

Provides ``SecurityDiagnostics`` for in-depth inspection of
security state including active identities, certificates,
policy evaluations, and mTLS sessions.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityDiagnostics:
    """Diagnostics for security components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._identity_registry: Dict[str, Dict[str, Any]] = {}
        self._certificate_registry: Dict[str, Dict[str, Any]] = {}
        self._mtls_sessions: Dict[str, Dict[str, Any]] = {}
        self._policy_evaluations: List[Dict[str, Any]] = []
        self._max_history = 500
        self._snapshot_count = 0

    def register_identity(self, identity_id: str, info: Dict[str, Any]) -> None:
        with self._lock:
            self._identity_registry[identity_id] = {
                **info,
                "_registered_at": datetime.utcnow().isoformat(),
            }

    def unregister_identity(self, identity_id: str) -> None:
        with self._lock:
            self._identity_registry.pop(identity_id, None)

    def register_certificate(self, cert_id: str, info: Dict[str, Any]) -> None:
        with self._lock:
            self._certificate_registry[cert_id] = {
                **info,
                "_registered_at": datetime.utcnow().isoformat(),
            }

    def unregister_certificate(self, cert_id: str) -> None:
        with self._lock:
            self._certificate_registry.pop(cert_id, None)

    def register_mtls_session(self, session_id: str, info: Dict[str, Any]) -> None:
        with self._lock:
            self._mtls_sessions[session_id] = {
                **info,
                "_started_at": datetime.utcnow().isoformat(),
            }

    def unregister_mtls_session(self, session_id: str) -> None:
        with self._lock:
            self._mtls_sessions.pop(session_id, None)

    def record_policy_evaluation(self, policy_id: str, principal: str, result: str, details: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._snapshot_count += 1
            self._policy_evaluations.append({
                "policy_id": policy_id,
                "principal": principal,
                "result": result,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._snapshot_count,
            })
            if len(self._policy_evaluations) > self._max_history:
                self._policy_evaluations = self._policy_evaluations[-self._max_history:]

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "identity_count": len(self._identity_registry),
                "certificate_count": len(self._certificate_registry),
                "mtls_session_count": len(self._mtls_sessions),
                "policy_evaluation_count": len(self._policy_evaluations),
                "snapshot_count": self._snapshot_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_snapshot()

    def clear(self) -> None:
        with self._lock:
            self._identity_registry.clear()
            self._certificate_registry.clear()
            self._mtls_sessions.clear()
            self._policy_evaluations.clear()
            self._snapshot_count = 0
