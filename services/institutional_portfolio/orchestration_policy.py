"""
Orchestration Policy — Rules Governing Portfolio Operations

Policies define allowed/disallowed orchestration actions:
- Max allowed netting ratio
- Min confidence for conflict resolution
- Rebalance frequency limits
- Capital conflict resolution strategy
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PolicyRule:
    rule_id: str
    category: str
    key: str
    value: Any
    description: str = ""


class OrchestrationPolicy:
    """
    Defines and enforces policies for portfolio orchestration.

    Policies control: netting aggressiveness, rebalance frequency,
    capital conflict resolution strategy, minimum confidence thresholds.
    """

    def __init__(
        self,
        policy_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.policy_id = policy_id or f"op-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._rules: Dict[str, PolicyRule] = {
            "max_netting_ratio": PolicyRule("r1", "netting", "max_ratio", 0.90, "Max gross exposure reduction via netting"),
            "min_signal_confidence": PolicyRule("r2", "signal", "min_confidence", 0.40, "Min confidence for signal execution"),
            "rebalance_cooldown_min": PolicyRule("r3", "rebalance", "cooldown_minutes", 120, "Min time between rebalances"),
            "capital_resolution_strategy": PolicyRule("r4", "capital", "resolution", "priority", "Priority vs efficiency strategy"),
            "max_turnover_pct": PolicyRule("r5", "turnover", "max_pct", 0.50, "Max portfolio turnover per rebalance"),
        }

    def get(self, key: str) -> Any:
        rule = self._rules.get(key)
        if rule:
            return rule.value
        return self.config.get(key)

    def set(self, key: str, value: Any) -> None:
        if key in self._rules:
            self._rules[key].value = value

    def get_all(self) -> Dict[str, Any]:
        return {k: r.value for k, r in self._rules.items()}
