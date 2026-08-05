"""Canary release for ICYQuant Service Mesh.

Provides ``CanaryRelease`` for percentage/header/cookie/user-group/
region-based canary routing decisions.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CanaryRule:
    """A canary routing rule."""

    def __init__(
        self,
        rule_id: str,
        canary_host: str,
        stable_host: str,
        percentage: float = 0.0,
        header_name: str = "",
        header_value: str = "",
        cookie_name: str = "",
        user_groups: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        self.rule_id = rule_id
        self.canary_host = canary_host
        self.stable_host = stable_host
        self.percentage = percentage
        self.header_name = header_name
        self.header_value = header_value
        self.cookie_name = cookie_name
        self.user_groups = user_groups or []
        self.regions = regions or []
        self.enabled = enabled
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "canary_host": self.canary_host,
            "stable_host": self.stable_host,
            "percentage": self.percentage,
            "header_name": self.header_name,
            "header_value": self.header_value,
            "cookie_name": self.cookie_name,
            "user_groups": self.user_groups,
            "regions": self.regions,
            "enabled": self.enabled,
        }


class CanaryRelease:
    """Manages canary release routing decisions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: Dict[str, CanaryRule] = {}
        self._decision_count = 0
        self._canary_count = 0
        self._stable_count = 0

    def add_rule(self, rule: CanaryRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def decide(
        self,
        rule_id: str,
        request_id: str = "",
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        user_group: str = "",
        region: str = "",
    ) -> Dict[str, Any]:
        """Decide whether to route to canary or stable."""
        with self._lock:
            self._decision_count += 1
            rule = self._rules.get(rule_id)

        if not rule or not rule.enabled:
            return {
                "target": "",
                "version": "",
                "is_canary": False,
                "reason": "rule_not_found_or_disabled",
            }

        headers = headers or {}
        cookies = cookies or {}

        # 1. Check header-based canary
        if rule.header_name and rule.header_value:
            header_val = headers.get(rule.header_name, "")
            if header_val == rule.header_value:
                self._canary_count += 1
                return {
                    "target": rule.canary_host,
                    "version": "canary",
                    "is_canary": True,
                    "reason": f"header:{rule.header_name}",
                }

        # 2. Check cookie-based canary
        if rule.cookie_name:
            cookie_val = cookies.get(rule.cookie_name, "")
            if cookie_val == "canary":
                self._canary_count += 1
                return {
                    "target": rule.canary_host,
                    "version": "canary",
                    "is_canary": True,
                    "reason": f"cookie:{rule.cookie_name}",
                }

        # 3. Check user group
        if rule.user_groups and user_group:
            if user_group in rule.user_groups:
                self._canary_count += 1
                return {
                    "target": rule.canary_host,
                    "version": "canary",
                    "is_canary": True,
                    "reason": f"user_group:{user_group}",
                }

        # 4. Check region
        if rule.regions and region:
            if region in rule.regions:
                self._canary_count += 1
                return {
                    "target": rule.canary_host,
                    "version": "canary",
                    "is_canary": True,
                    "reason": f"region:{region}",
                }

        # 5. Check percentage
        if rule.percentage > 0 and request_id:
            hash_val = int(
                hashlib.md5(
                    request_id.encode()
                ).hexdigest(),
                16,
            )
            if (hash_val % 10000) / 100.0 < rule.percentage:
                self._canary_count += 1
                return {
                    "target": rule.canary_host,
                    "version": "canary",
                    "is_canary": True,
                    "reason": f"percentage:{rule.percentage}",
                }

        self._stable_count += 1
        return {
            "target": rule.stable_host,
            "version": "stable",
            "is_canary": False,
            "reason": "default_stable",
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._canary_count + self._stable_count
            canary_rate = (
                self._canary_count / total if total > 0 else 0.0
            )
            return {
                "rule_count": len(self._rules),
                "decision_count": self._decision_count,
                "canary_count": self._canary_count,
                "stable_count": self._stable_count,
                "canary_rate": canary_rate,
            }
