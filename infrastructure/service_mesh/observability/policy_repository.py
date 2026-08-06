"""Policy repository for ICYQuant Service Mesh observability.

Provides ``RuntimePolicyRepository`` for storing, versioning,
and rolling back runtime observability policies.
"""

from __future__ import annotations

import copy
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuntimePolicy:
    """A runtime observability policy."""

    def __init__(
        self,
        policy_id: str,
        policy_type: str = "traffic",
        enabled: bool = True,
        priority: int = 50,
        config: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> None:
        self.policy_id = policy_id
        self.policy_type = policy_type
        self.enabled = enabled
        self.priority = priority
        self.config = config or {}
        self.description = description
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.version = 1

    def update(self, config: Dict[str, Any]) -> None:
        self.config.update(config)
        self.updated_at = datetime.utcnow()
        self.version += 1

    def enable(self) -> None:
        self.enabled = True
        self.updated_at = datetime.utcnow()

    def disable(self) -> None:
        self.enabled = False
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type,
            "enabled": self.enabled,
            "priority": self.priority,
            "config": dict(self.config),
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuntimePolicy:
        policy = cls(
            policy_id=data["policy_id"],
            policy_type=data.get("policy_type", "traffic"),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 50),
            config=data.get("config", {}),
            description=data.get("description", ""),
        )
        return policy


class RuntimePolicyRepository:
    """Repository for runtime policies with versioning."""

    def __init__(self, max_versions: int = 50) -> None:
        self._max_versions = max_versions
        self._lock = threading.RLock()
        self._policies: Dict[str, RuntimePolicy] = {}
        self._versions: List[Dict[str, Any]] = []
        self._current_version = 0

    def add(self, policy: RuntimePolicy) -> None:
        with self._lock:
            self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> Optional[RuntimePolicy]:
        with self._lock:
            return self._policies.get(policy_id)

    def remove(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False

    def list_all(self) -> List[RuntimePolicy]:
        with self._lock:
            return list(self._policies.values())

    def list_by_type(self, policy_type: str) -> List[RuntimePolicy]:
        with self._lock:
            return [
                p for p in self._policies.values()
                if p.policy_type == policy_type
            ]

    def list_enabled(self) -> List[RuntimePolicy]:
        with self._lock:
            return [p for p in self._policies.values() if p.enabled]

    def update(self, policy_id: str, config: Dict[str, Any]) -> bool:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy:
                policy.update(config)
                return True
            return False

    def enable(self, policy_id: str) -> bool:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy:
                policy.enable()
                return True
            return False

    def disable(self, policy_id: str) -> bool:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy:
                policy.disable()
                return True
            return False

    def commit_version(self) -> int:
        """Commit current state as a version."""
        with self._lock:
            snapshot = {
                p.policy_id: copy.deepcopy(p.to_dict())
                for p in self._policies.values()
            }
            self._current_version += 1
            version = {
                "version": self._current_version,
                "timestamp": datetime.utcnow().isoformat(),
                "policies": snapshot,
            }
            self._versions.append(version)
            if len(self._versions) > self._max_versions:
                self._versions = self._versions[-self._max_versions:]
            return self._current_version

    def rollback(self, version: int) -> bool:
        with self._lock:
            target = None
            for v in self._versions:
                if v["version"] == version:
                    target = v
                    break
            if not target:
                return False
            self._policies.clear()
            for pid, pdata in target["policies"].items():
                policy = RuntimePolicy.from_dict(pdata)
                self._policies[pid] = policy
            self._current_version = version
            return True

    def list_versions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"version": v["version"], "timestamp": v["timestamp"]}
                for v in self._versions
            ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy_count": len(self._policies),
                "enabled_count": sum(1 for p in self._policies.values() if p.enabled),
                "version_count": len(self._versions),
                "current_version": self._current_version,
            }

    def clear(self) -> None:
        with self._lock:
            self._policies.clear()
            self._versions.clear()
            self._current_version = 0
