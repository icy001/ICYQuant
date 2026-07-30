"""Policy Engine - controls AI agent behavior boundaries and risk limits.

Defines hard and soft constraints on agent actions:
- Position limits per symbol
- Sector exposure limits
- Daily loss limits
- Drawdown-based circuit breakers
- Volatility-based leverage adjustments
- Minimum confidence thresholds
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PolicyAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    REDUCE = "reduce"
    BLOCK = "block"
    STOP = "stop"  # circuit breaker - halt all trading


class PolicyType(Enum):
    POSITION_LIMIT = "position_limit"
    SECTOR_EXPOSURE = "sector_exposure"
    DAILY_LOSS = "daily_loss"
    DRAWDOWN = "drawdown"
    CONFIDENCE = "confidence"
    VOLATILITY = "volatility"
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    FREQUENCY = "frequency"


@dataclass
class PolicyRule:
    """A single policy rule that constrains agent behavior."""

    rule_id: str
    rule_type: PolicyType
    description: str
    condition: str  # Human-readable condition
    action: PolicyAction = PolicyAction.WARN
    priority: int = 50  # 0-100, higher = more important
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: Dict[str, Any]) -> PolicyAction:
        """Evaluate this rule against the current context."""
        if not self.enabled:
            return PolicyAction.ALLOW
        try:
            return self._evaluate_impl(context)
        except Exception:
            logger.exception("Policy rule evaluation error: %s", self.rule_id)
            return PolicyAction.ALLOW

    def _evaluate_impl(self, context: Dict[str, Any]) -> PolicyAction:
        """Default evaluation logic based on rule type."""
        if self.rule_type == PolicyType.POSITION_LIMIT:
            max_pct = self.params.get("max_position_pct", 10.0)
            current_pct = context.get("position_pct", 0)
            if current_pct > max_pct:
                return PolicyAction.BLOCK
            if current_pct > max_pct * 0.8:
                return PolicyAction.WARN
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.SECTOR_EXPOSURE:
            max_pct = self.params.get("max_sector_pct", 40.0)
            current_pct = context.get("sector_exposure_pct", 0)
            if current_pct > max_pct:
                return PolicyAction.BLOCK
            if current_pct > max_pct * 0.85:
                return PolicyAction.WARN
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.DAILY_LOSS:
            max_loss_pct = self.params.get("max_daily_loss_pct", 3.0)
            daily_pnl_pct = context.get("daily_pnl_pct", 0)
            if abs(daily_pnl_pct) > max_loss_pct and daily_pnl_pct < 0:
                return PolicyAction.STOP
            if abs(daily_pnl_pct) > max_loss_pct * 0.7 and daily_pnl_pct < 0:
                return PolicyAction.BLOCK
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.DRAWDOWN:
            max_dd_pct = self.params.get("max_drawdown_pct", 10.0)
            current_dd = context.get("current_drawdown_pct", 0)
            if abs(current_dd) > max_dd_pct:
                return PolicyAction.STOP
            if abs(current_dd) > max_dd_pct * 0.7:
                return PolicyAction.REDUCE
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.CONFIDENCE:
            min_confidence = self.params.get("min_confidence", 0.6)
            confidence = context.get("confidence", 0)
            if confidence < min_confidence:
                return PolicyAction.BLOCK
            if confidence < min_confidence + 0.1:
                return PolicyAction.REDUCE
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.VOLATILITY:
            max_vol = self.params.get("max_volatility", 40.0)
            current_vol = context.get("volatility", 20)
            if current_vol > max_vol:
                return PolicyAction.REDUCE
            if current_vol > max_vol * 0.75:
                return PolicyAction.WARN
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.LEVERAGE:
            max_lev = self.params.get("max_leverage", 1.0)
            current_lev = context.get("leverage", 0)
            if current_lev > max_lev:
                return PolicyAction.BLOCK
            if current_lev > max_lev * 0.85:
                return PolicyAction.REDUCE
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.CONCENTRATION:
            max_conc = self.params.get("max_concentration", 25.0)
            top_holding_pct = context.get("top_holding_pct", 0)
            if top_holding_pct > max_conc:
                return PolicyAction.BLOCK
            if top_holding_pct > max_conc * 0.8:
                return PolicyAction.WARN
            return PolicyAction.ALLOW

        elif self.rule_type == PolicyType.FREQUENCY:
            max_trades_per_hour = self.params.get("max_trades_per_hour", 20)
            current_trades = context.get("trades_this_hour", 0)
            if current_trades >= max_trades_per_hour:
                return PolicyAction.BLOCK
            if current_trades >= max_trades_per_hour * 0.8:
                return PolicyAction.WARN
            return PolicyAction.ALLOW

        return PolicyAction.ALLOW


class PolicyEngine:
    """Engine that evaluates policies and enforces constraints on agent decisions.

    Checks every proposed action against all applicable rules before execution.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._rules: List[PolicyRule] = []
        self._violations: List[Dict[str, Any]] = []
        self._max_violations = 5000
        self._circuit_breaker_triggered = False
        self._circuit_breaker_time: Optional[float] = None
        self._circuit_breaker_cooldown = 300  # 5 minutes

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule."""
        # Replace if same ID exists
        for i, existing in enumerate(self._rules):
            if existing.rule_id == rule.rule_id:
                self._rules[i] = rule
                return
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a policy rule."""
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        """Get a specific rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    def evaluate(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate all rules against a decision context.

        Returns the most restrictive action across all rules.
        """
        if self._circuit_breaker_triggered:
            # Check if cooldown expired
            if self._circuit_breaker_time:
                elapsed = time.time() - self._circuit_breaker_time
                if elapsed >= self._circuit_breaker_cooldown:
                    self._circuit_breaker_triggered = False
                    self._circuit_breaker_time = None
                    logger.info("Circuit breaker cooldown expired")
                else:
                    return {
                        "action": PolicyAction.STOP.value,
                        "reason": "Circuit breaker active",
                        "rule_violations": [],
                        "remaining_cooldown": self._circuit_breaker_cooldown - elapsed,
                    }

        action_order = {
            PolicyAction.ALLOW: 0,
            PolicyAction.WARN: 1,
            PolicyAction.REDUCE: 2,
            PolicyAction.BLOCK: 3,
            PolicyAction.STOP: 4,
        }

        most_restrictive = PolicyAction.ALLOW
        violations = []
        reasons = []

        for rule in self._rules:
            result = rule.evaluate(context)
            if result != PolicyAction.ALLOW:
                violations.append({
                    "rule_id": rule.rule_id,
                    "rule_type": rule.rule_type.value,
                    "action": result.value,
                    "description": rule.description,
                    "priority": rule.priority,
                })
                reasons.append(f"[{rule.rule_type.value}] {rule.description}")
                if action_order[result] > action_order[most_restrictive]:
                    most_restrictive = result

        # Record violations
        if violations:
            self._violations.append({
                "timestamp": time.time(),
                "context": context,
                "violations": violations,
                "final_action": most_restrictive.value,
            })
            if len(self._violations) > self._max_violations:
                self._violations = self._violations[-self._max_violations:]

        # Trigger circuit breaker on STOP
        if most_restrictive == PolicyAction.STOP:
            self._circuit_breaker_triggered = True
            self._circuit_breaker_time = time.time()
            logger.critical("Circuit breaker triggered! All trading halted.")

        return {
            "action": most_restrictive.value,
            "allowed": most_restrictive in (PolicyAction.ALLOW, PolicyAction.WARN),
            "blocked": most_restrictive in (PolicyAction.BLOCK, PolicyAction.STOP),
            "reason": "; ".join(reasons) if reasons else "All checks passed",
            "rule_violations": violations,
        }

    def check_decision(
        self,
        symbol: str,
        action: str,
        size_pct: float,
        confidence: float,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Quick check for a trading decision.

        Convenience method that builds context and evaluates.
        """
        ctx = {
            "symbol": symbol,
            "action": action,
            "position_pct": size_pct,
            "confidence": confidence,
        }
        if context:
            ctx.update(context)
        return self.evaluate(ctx)

    # ── Default Rules ───────────────────────────────────────────

    @classmethod
    def create_default_engine(cls) -> "PolicyEngine":
        """Create a PolicyEngine with standard institutional rules."""
        engine = cls(name="default")
        engine.add_rules(cls.default_rules())
        return engine

    def add_rules(self, rules: List[PolicyRule]) -> None:
        """Add multiple rules at once."""
        for rule in rules:
            self.add_rule(rule)

    @staticmethod
    def default_rules() -> List[PolicyRule]:
        """Standard institutional policy rules."""
        return [
            PolicyRule(
                rule_id="POSITION_LIMIT",
                rule_type=PolicyType.POSITION_LIMIT,
                description="Max 10% per single position",
                condition="position_pct > max_position_pct",
                action=PolicyAction.BLOCK,
                priority=90,
                params={"max_position_pct": 10.0},
            ),
            PolicyRule(
                rule_id="SECTOR_EXPOSURE",
                rule_type=PolicyType.SECTOR_EXPOSURE,
                description="Max 40% per sector",
                condition="sector_exposure_pct > max_sector_pct",
                action=PolicyAction.BLOCK,
                priority=85,
                params={"max_sector_pct": 40.0},
            ),
            PolicyRule(
                rule_id="DAILY_LOSS_LIMIT",
                rule_type=PolicyType.DAILY_LOSS,
                description="Stop trading if daily loss exceeds 3%",
                condition="abs(daily_pnl_pct) > max_daily_loss_pct and daily_pnl_pct < 0",
                action=PolicyAction.STOP,
                priority=100,
                params={"max_daily_loss_pct": 3.0},
            ),
            PolicyRule(
                rule_id="DRAWDOWN_LIMIT",
                rule_type=PolicyType.DRAWDOWN,
                description="Reduce positions if drawdown exceeds 7%, stop at 10%",
                condition="abs(current_drawdown_pct) > max_drawdown_pct",
                action=PolicyAction.STOP,
                priority=95,
                params={"max_drawdown_pct": 10.0},
            ),
            PolicyRule(
                rule_id="MIN_CONFIDENCE",
                rule_type=PolicyType.CONFIDENCE,
                description="Block trades with confidence below 60%",
                condition="confidence < min_confidence",
                action=PolicyAction.BLOCK,
                priority=80,
                params={"min_confidence": 0.6},
            ),
            PolicyRule(
                rule_id="VOLATILITY_REDUCE",
                rule_type=PolicyType.VOLATILITY,
                description="Reduce position sizes in high volatility (>40%)",
                condition="volatility > max_volatility",
                action=PolicyAction.REDUCE,
                priority=70,
                params={"max_volatility": 40.0},
            ),
            PolicyRule(
                rule_id="LEVERAGE_LIMIT",
                rule_type=PolicyType.LEVERAGE,
                description="No leverage allowed",
                condition="leverage > max_leverage",
                action=PolicyAction.BLOCK,
                priority=88,
                params={"max_leverage": 1.0},
            ),
            PolicyRule(
                rule_id="CONCENTRATION_LIMIT",
                rule_type=PolicyType.CONCENTRATION,
                description="Max 25% in any single holding",
                condition="top_holding_pct > max_concentration",
                action=PolicyAction.BLOCK,
                priority=82,
                params={"max_concentration": 25.0},
            ),
            PolicyRule(
                rule_id="TRADING_FREQUENCY",
                rule_type=PolicyType.FREQUENCY,
                description="Max 20 trades per hour",
                condition="trades_this_hour >= max_trades_per_hour",
                action=PolicyAction.BLOCK,
                priority=60,
                params={"max_trades_per_hour": 20},
            ),
        ]

    # ── Query Methods ───────────────────────────────────────────

    def get_violations(
        self, limit: int = 50, rule_type: Optional[PolicyType] = None
    ) -> List[Dict[str, Any]]:
        """Get recent policy violations."""
        results = []
        for v in reversed(self._violations):
            if rule_type:
                if not any(r["rule_type"] == rule_type.value for r in v["violations"]):
                    continue
            results.append(v)
            if len(results) >= limit:
                break
        return list(reversed(results))

    def get_rules_by_type(self, rule_type: PolicyType) -> List[PolicyRule]:
        """Get all rules of a specific type."""
        return [r for r in self._rules if r.rule_type == rule_type]

    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is currently active."""
        return self._circuit_breaker_triggered

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_breaker_triggered = False
        self._circuit_breaker_time = None
        logger.info("Circuit breaker manually reset")

    def get_status(self) -> Dict[str, Any]:
        """Get policy engine status."""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "circuit_breaker": self._circuit_breaker_triggered,
            "violations_count": len(self._violations),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "type": r.rule_type.value,
                    "enabled": r.enabled,
                    "action": r.action.value,
                    "priority": r.priority,
                }
                for r in self._rules
            ],
        }

    def clear(self) -> None:
        """Clear all rules and violations."""
        self._rules.clear()
        self._violations.clear()
        self._circuit_breaker_triggered = False
        self._circuit_breaker_time = None
