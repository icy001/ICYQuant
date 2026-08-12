"""
DetectionRegistry — pluggable store of DetectionRules.

Rules are not hard-coded into the engine: adding a new risk / execution /
market rule never requires touching the Detection Engine (spec section 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .detection_rule import DetectionRule


@dataclass
class DetectionRegistry:
    _rules: Dict[str, DetectionRule] = field(default_factory=dict)

    # -- writes ----------------------------------------------------------

    def register(self, rule: DetectionRule) -> None:
        self._rules[rule.rule_id] = rule

    def unregister(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def enable(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule is None:
            return False
        rule.enabled = True
        return True

    def disable(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule is None:
            return False
        rule.enabled = False
        return True

    # -- queries ---------------------------------------------------------

    def get(self, rule_id: str) -> Optional[DetectionRule]:
        return self._rules.get(rule_id)

    def list(self) -> List[DetectionRule]:
        return list(self._rules.values())

    def list_for_event_type(self, event_type: str) -> List[DetectionRule]:
        """Enabled rules for an event type, highest priority first."""
        return sorted(
            (r for r in self._rules.values() if r.enabled and r.event_type == event_type),
            key=lambda r: r.priority,
        )

    def rule_count(self) -> int:
        return len(self._rules)

    def clear(self) -> None:
        self._rules.clear()
