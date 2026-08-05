"""Sandbox policy engine.

Provides :class:`SandboxPolicy` for managing per-plugin
security policies, :class:`PolicyEngine` for evaluating
policy rules, :class:`PolicyDecision` for representing
evaluation outcomes, and :class:`PolicyRule` for defining
pattern-based policy rules.
"""

from __future__ import annotations

import fnmatch
import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..exceptions import PluginSandboxViolationError

logger = logging.getLogger(__name__)


class PolicyDecision(Enum):
    """Represents the outcome of a policy evaluation.

    Attributes:
        ALLOW: The action is permitted.
        DENY: The action is forbidden.
        REQUIRE_APPROVAL: The action requires manual approval.
    """

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyRule:
    """A single pattern-based policy rule.

    Rules are evaluated in order; the first matching rule
    determines the :class:`PolicyDecision`.  Patterns support
    shell-style wildcards (``*``, ``?``) via :func:`fnmatch`.

    Attributes:
        action_pattern: Glob pattern for the action name
            (e.g. ``"filesystem.*"``).
        decision: The decision to apply when the rule matches.
        plugin_pattern: Optional glob pattern for plugin_id.
        resource_pattern: Optional glob pattern for the resource.
        description: Human-readable description of the rule.
        enabled: Whether the rule is active.
    """

    def __init__(
        self,
        action_pattern: str,
        decision: PolicyDecision,
        plugin_pattern: str = "*",
        resource_pattern: str = "*",
        description: str = "",
        enabled: bool = True,
    ) -> None:
        self.action_pattern = action_pattern
        self.decision = decision
        self.plugin_pattern = plugin_pattern
        self.resource_pattern = resource_pattern
        self.description = description
        self.enabled = enabled
        self._created_at = time.time()

    def matches(
        self,
        action: str,
        plugin_id: str,
        resource: str = "",
    ) -> bool:
        """Check whether this rule matches the given parameters.

        Args:
            action: The action name (e.g. ``"filesystem.read"``).
            plugin_id: The plugin identifier.
            resource: Optional resource identifier.

        Returns:
            True if all patterns match.
        """
        if not self.enabled:
            return False
        if not fnmatch.fnmatch(action, self.action_pattern):
            return False
        if not fnmatch.fnmatch(plugin_id, self.plugin_pattern):
            return False
        if resource and self.resource_pattern != "*":
            if not fnmatch.fnmatch(resource, self.resource_pattern):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the rule to a dictionary.

        Returns:
            A dictionary representation of the rule.
        """
        return {
            "action_pattern": self.action_pattern,
            "decision": self.decision.value,
            "plugin_pattern": self.plugin_pattern,
            "resource_pattern": self.resource_pattern,
            "description": self.description,
            "enabled": self.enabled,
            "created_at": self._created_at,
        }


class SandboxPolicy:
    """Manages per-plugin sandbox security policies.

    Provides an in-memory policy store with global defaults
    and per-plugin overrides.  By default, all actions are
    denied; explicit allow rules are required.

    Policy actions follow the format:
    ``<category>.<operation>``, e.g.:

    - ``filesystem.read``
    - ``filesystem.write``
    - ``network.outbound``
    - ``secrets.read``
    - ``cpu.heavy``
    - ``memory.limit``

    Attributes:
        _policies: Maps plugin_id to its policy configuration.
        _global_default: The default policy applied to all plugins.
        _enforced: Maps plugin_id to enforcement flag.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._global_default: Dict[str, Any] = {
            "default_action": "deny",
            "allowed_actions": [],
            "denied_actions": [],
        }
        self._enforced: Dict[str, bool] = {}
        self._lock = threading.RLock()

    def allow(
        self,
        action: str,
        plugin_id: str,
        resource: str = "",
    ) -> bool:
        """Check whether an action is allowed for a plugin.

        Evaluates the plugin's policy (or the global default)
        to determine if the action is permitted.

        Args:
            action: The action string (e.g. ``"filesystem.read"``).
            plugin_id: Unique identifier for the plugin.
            resource: Optional resource identifier.

        Returns:
            True if the action is allowed, False otherwise.
        """
        with self._lock:
            policy = self._policies.get(
                plugin_id, self._global_default
            )

            denied_actions = policy.get("denied_actions", [])
            if action in denied_actions:
                return False

            allowed_actions = policy.get("allowed_actions", [])
            if action in allowed_actions:
                return True

            default_action = policy.get("default_action", "deny")
            return default_action == "allow"

    def deny(
        self,
        action: str,
        plugin_id: str,
        reason: str = "",
    ) -> None:
        """Explicitly deny an action for a plugin.

        Args:
            action: The action to deny.
            plugin_id: Unique identifier for the plugin.
            reason: Optional reason for the denial.
        """
        with self._lock:
            policy = self._policies.setdefault(plugin_id, {})
            denied = policy.setdefault("denied_actions", [])
            if action not in denied:
                denied.append(action)
            logger.debug(
                "Denied action '%s' for plugin %s: %s",
                action, plugin_id, reason,
            )

    def set_policy(
        self,
        plugin_id: str,
        policy: Dict[str, Any],
    ) -> None:
        """Set the complete policy for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            policy: A policy dictionary with optional keys:
                - ``default_action``: ``"allow"`` or ``"deny"``.
                - ``allowed_actions``: List of allowed action strings.
                - ``denied_actions``: List of denied action strings.
        """
        with self._lock:
            self._policies[plugin_id] = {
                "default_action": policy.get(
                    "default_action", "deny"
                ),
                "allowed_actions": list(
                    policy.get("allowed_actions", [])
                ),
                "denied_actions": list(
                    policy.get("denied_actions", [])
                ),
            }
            logger.info(
                "Set policy for plugin %s", plugin_id
            )

    def get_policy(self, plugin_id: str) -> Dict[str, Any]:
        """Get the current policy for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            The policy dictionary, or the global default if
            no per-plugin policy is set.
        """
        with self._lock:
            return dict(
                self._policies.get(
                    plugin_id, self._global_default
                )
            )

    def reset_policy(self, plugin_id: str) -> None:
        """Reset a plugin's policy to the global default.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._policies.pop(plugin_id, None)
            self._enforced.pop(plugin_id, None)
            logger.info(
                "Reset policy for plugin %s", plugin_id
            )

    def get_all_policies(self) -> Dict[str, Dict[str, Any]]:
        """Get all per-plugin policies.

        Returns:
            A dictionary mapping plugin_id to its policy.
        """
        with self._lock:
            return {
                pid: dict(policy)
                for pid, policy in self._policies.items()
            }

    def is_enforced(self, plugin_id: str) -> bool:
        """Check whether sandbox policy is enforced for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            True if enforcement is active (default: True).
        """
        with self._lock:
            return self._enforced.get(plugin_id, True)

    def set_enforced(
        self, plugin_id: str, enforced: bool
    ) -> None:
        """Enable or disable policy enforcement for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            enforced: Whether to enforce the policy.
        """
        with self._lock:
            self._enforced[plugin_id] = enforced
            logger.info(
                "Policy enforcement for plugin %s: %s",
                plugin_id,
                "enforced",
            )

    def set_global_default(
        self, policy: Dict[str, Any]
    ) -> None:
        """Set the global default policy.

        Args:
            policy: A policy dictionary (see :meth:`set_policy`).
        """
        with self._lock:
            self._global_default = {
                "default_action": policy.get(
                    "default_action", "deny"
                ),
                "allowed_actions": list(
                    policy.get("allowed_actions", [])
                ),
                "denied_actions": list(
                    policy.get("denied_actions", [])
                ),
            }
            logger.info("Set global default policy")

    def get_stats(self) -> Dict[str, Any]:
        """Get policy store statistics.

        Returns:
            A dictionary with policy counts and enforcement
            status.
        """
        with self._lock:
            enforced_count = sum(
                1
                for v in self._enforced.values()
                if v
            )
            return {
                "total_policies": len(self._policies),
                "enforced_plugins": enforced_count,
                "plugins_without_enforcement": len(
                    self._enforced
                )
                - enforced_count,
                "global_default": dict(self._global_default),
                "plugins": sorted(self._policies.keys()),
            }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the policy store to a dictionary.

        Returns:
            A dictionary with all policies and configuration.
        """
        with self._lock:
            return {
                "global_default": dict(self._global_default),
                "policies": {
                    pid: dict(p)
                    for pid, p in self._policies.items()
                },
                "enforced": dict(self._enforced),
            }


class PolicyEngine:
    """Evaluates policy rules to produce :class:`PolicyDecision` s.

    Supports chaining multiple rules; rules are evaluated in
    insertion order and the first match determines the decision.

    Attributes:
        _rules: Ordered list of policy rules.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._rules: List[PolicyRule] = []
        self._lock = threading.RLock()

    def evaluate(
        self,
        plugin_id: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate policy rules for a given action.

        Rules are evaluated in order; the first matching rule's
        decision is returned.  If no rule matches, the default
        decision is :attr:`PolicyDecision.DENY`.

        Args:
            plugin_id: Unique identifier for the plugin.
            action: The action string (e.g. ``"filesystem.read"``).
            context: Optional evaluation context with keys such
                as ``resource``, ``user``, ``time``, etc.

        Returns:
            The resulting :class:`PolicyDecision`.
        """
        context = context or {}
        resource = context.get("resource", "")

        with self._lock:
            for rule in self._rules:
                if rule.matches(action, plugin_id, resource):
                    logger.debug(
                        "Rule matched: action=%s plugin=%s "
                        "decision=%s",
                        action,
                        plugin_id,
                        rule.decision.value,
                    )
                    return rule.decision

            logger.debug(
                "No rule matched for action=%s plugin=%s; "
                "defaulting to DENY",
                action,
                plugin_id,
            )
            return PolicyDecision.DENY

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule to the engine.

        Args:
            rule: The :class:`PolicyRule` to add.
        """
        with self._lock:
            self._rules.append(rule)
            logger.debug(
                "Added policy rule: %s → %s",
                rule.action_pattern,
                rule.decision.value,
            )

    def remove_rule(self, rule: PolicyRule) -> bool:
        """Remove a policy rule from the engine.

        Args:
            rule: The :class:`PolicyRule` to remove.

        Returns:
            True if the rule was found and removed.
        """
        with self._lock:
            try:
                self._rules.remove(rule)
                return True
            except ValueError:
                return False

    def get_rules(self) -> List[PolicyRule]:
        """Get all policy rules.

        Returns:
            A copy of the ordered rule list.
        """
        with self._lock:
            return list(self._rules)

    def clear_rules(self) -> None:
        """Remove all policy rules."""
        with self._lock:
            self._rules.clear()
            logger.info("Cleared all policy rules")

    def set_rules(self, rules: List[PolicyRule]) -> None:
        """Replace all policy rules with a new list.

        Args:
            rules: The new list of :class:`PolicyRule` objects.
        """
        with self._lock:
            self._rules = list(rules)
            logger.info(
                "Replaced policy rules (%d rules)", len(rules)
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get policy engine statistics.

        Returns:
            A dictionary with rule counts and summary.
        """
        with self._lock:
            enabled = sum(
                1 for r in self._rules if r.enabled
            )
            decisions: Dict[str, int] = {}
            for r in self._rules:
                d = r.decision.value
                decisions[d] = decisions.get(d, 0) + 1
            return {
                "total_rules": len(self._rules),
                "enabled_rules": enabled,
                "disabled_rules": len(self._rules) - enabled,
                "rules_by_decision": decisions,
            }