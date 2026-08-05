"""Traffic mirroring for ICYQuant Service Mesh.

Provides ``TrafficMirror`` for duplicating requests to mirror
services without affecting production traffic.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MirrorPolicy:
    """A traffic mirroring policy."""

    def __init__(
        self,
        policy_id: str,
        mirror_host: str,
        mirror_path: str = "",
        percentage: float = 100.0,
        include_headers: Optional[List[str]] = None,
        exclude_headers: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        self.policy_id = policy_id
        self.mirror_host = mirror_host
        self.mirror_path = mirror_path
        self.percentage = percentage
        self.include_headers = include_headers or []
        self.exclude_headers = exclude_headers or []
        self.enabled = enabled
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "mirror_host": self.mirror_host,
            "mirror_path": self.mirror_path,
            "percentage": self.percentage,
            "include_headers": self.include_headers,
            "exclude_headers": self.exclude_headers,
            "enabled": self.enabled,
        }


class TrafficMirror:
    """Manages traffic mirroring."""

    def __init__(
        self,
        mirror_fn: Optional[Callable] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._policies: Dict[str, MirrorPolicy] = {}
        self._mirror_fn = mirror_fn or self._default_mirror
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_latency = 0.0

    def _default_mirror(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Any,
        mirror_host: str,
        mirror_path: str,
    ) -> Dict[str, Any]:
        """Default mirror implementation (stub)."""
        return {
            "status": 200,
            "mirror_host": mirror_host,
            "mirror_path": mirror_path,
        }

    def add_policy(self, policy: MirrorPolicy) -> None:
        with self._lock:
            self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False

    async def mirror_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
        policy_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Mirror a request to all matching mirror policies."""
        headers = headers or {}
        results = []

        with self._lock:
            policies_to_apply: List[MirrorPolicy] = []
            if policy_ids:
                for pid in policy_ids:
                    p = self._policies.get(pid)
                    if p and p.enabled:
                        policies_to_apply.append(p)
            else:
                for p in self._policies.values():
                    if p.enabled:
                        policies_to_apply.append(p)

        for policy in policies_to_apply:
            start = time.monotonic()
            try:
                mirror_path = policy.mirror_path or path
                filtered_headers = self._filter_headers(
                    headers,
                    policy.include_headers,
                    policy.exclude_headers,
                )
                result = self._mirror_fn(
                    method,
                    mirror_path,
                    filtered_headers,
                    body,
                    policy.mirror_host,
                    mirror_path,
                )
                duration = time.monotonic() - start

                with self._lock:
                    self._request_count += 1
                    self._success_count += 1
                    self._total_latency += duration

                results.append({
                    "policy_id": policy.policy_id,
                    "mirror_host": policy.mirror_host,
                    "status": result.get("status", 0),
                    "duration_s": duration,
                    "success": True,
                })
            except Exception as exc:
                duration = time.monotonic() - start
                with self._lock:
                    self._request_count += 1
                    self._failure_count += 1
                    self._total_latency += duration
                results.append({
                    "policy_id": policy.policy_id,
                    "mirror_host": policy.mirror_host,
                    "error": str(exc),
                    "duration_s": duration,
                    "success": False,
                })

        return results

    def _filter_headers(
        self,
        headers: Dict[str, str],
        include: List[str],
        exclude: List[str],
    ) -> Dict[str, str]:
        if include:
            return {
                k: v
                for k, v in headers.items()
                if k in include
            }
        elif exclude:
            return {
                k: v
                for k, v in headers.items()
                if k not in exclude
            }
        return dict(headers)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._request_count
            avg_latency = (
                self._total_latency / total if total > 0 else 0.0
            )
            success_rate = (
                self._success_count / total
                if total > 0
                else 0.0
            )
            return {
                "policy_count": len(self._policies),
                "request_count": total,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "success_rate": success_rate,
                "avg_latency_s": avg_latency,
            }