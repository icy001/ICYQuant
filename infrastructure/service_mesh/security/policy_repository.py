"""Policy repository for ICYQuant Service Mesh.

Provides ``PolicyRepository`` for storing, retrieving, and managing
security policies with versioning support.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .policy_engine import SecurityPolicy

logger = logging.getLogger(__name__)


class PolicyVersion:
    """A versioned snapshot of policies."""

    def __init__(self, version: int, policies: List[SecurityPolicy]) -> None:
        self.version = version
        self.policies = {p.policy_id: p for p in policies}
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "policy_count": len(self.policies),
            "created_at": self.created_at.isoformat(),
            "policy_ids": list(self.policies.keys()),
        }


class PolicyRepository:
    """Versioned policy repository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: Dict[str, SecurityPolicy] = {}
        self._versions: List[PolicyVersion] = []
        self._current_version = 0
        self._update_count = 0

    def add(self, policy: SecurityPolicy) -> None:
        with self._lock:
            self._policies[policy.policy_id] = policy
            self._update_count += 1

    def remove(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                self._update_count += 1
                return True
            return False

    def get(self, policy_id: str) -> Optional[SecurityPolicy]:
        with self._lock:
            return self._policies.get(policy_id)

    def list_all(self) -> List[SecurityPolicy]:
        with self._lock:
            return list(self._policies.values())

    def commit_version(self) -> int:
        """Commit current policies as a new version."""
        with self._lock:
            self._current_version += 1
            version = PolicyVersion(
                self._current_version,
                list(self._policies.values()),
            )
            self._versions.append(version)
        logger.info("Policy version %d committed (%d policies)", self._current_version, len(version.policies))
        return self._current_version

    def rollback(self, version: int) -> bool:
        """Rollback to a previous version."""
        with self._lock:
            target = None
            for v in self._versions:
                if v.version == version:
                    target = v
                    break
            if not target:
                return False
            self._policies = dict(target.policies)
            self._current_version = version
            self._update_count += 1
        logger.info("Rolled back to policy version %d", version)
        return True

    def list_versions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [v.to_dict() for v in self._versions]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy_count": len(self._policies),
                "version_count": len(self._versions),
                "current_version": self._current_version,
                "update_count": self._update_count,
            }
