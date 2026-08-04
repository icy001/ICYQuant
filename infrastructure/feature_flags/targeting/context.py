"""
Targeting context adapter.

Provides the context object for rule-based
targeting evaluation. TargetContext wraps
FeatureContext and provides structured
attributes for rule matching.

Rather than requiring callers to pass a
different context type, the targeting engine
accepts FeatureContext and adapts it into
TargetContext internally.

Example:
    ctx = TargetContext.from_feature_context(
        feature_context=FeatureContext(
            target_id="acc_001",
            attributes={"account_id": "001", "broker": "IBKR"},
        ),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

from ..models import FeatureContext


@dataclass
class TargetContext:
    """
    Context adapted for targeting rule evaluation.

    Provides structured attributes that rules
    can reference via attribute names. Can be
    created from a FeatureContext for seamless
    integration.

    Attributes:
        account_id: Account identifier.
        strategy_id: Strategy identifier.
        user_id: User identifier.
        broker: Broker name.
        exchange: Exchange name.
        environment: Deployment environment.
        account_type: Account type (e.g. "simulation", "live").
        tags: Set of tags for tag-based matching.
        attributes: Arbitrary additional attributes.
        target_id: Primary target identifier.
        target_type: Type of target.
    """

    account_id: str = ""
    strategy_id: str = ""
    user_id: str = ""
    broker: str = ""
    exchange: str = ""
    environment: str = "development"
    account_type: str = ""
    tags: FrozenSet[str] = field(default_factory=frozenset)
    attributes: Dict[str, Any] = field(default_factory=dict)
    target_id: str = ""
    target_type: str = ""

    @classmethod
    def from_feature_context(
        cls,
        feature_context: Optional[FeatureContext],
    ) -> "TargetContext":
        """
        Create a TargetContext from a FeatureContext.

        Extracts known attributes from the context's
        attributes dict and maps them to structured
        fields. Unknown attributes are preserved in
        the attributes dict for custom rule matching.

        Args:
            feature_context: The source FeatureContext.

        Returns:
            Adapted TargetContext.
        """
        if feature_context is None:
            return cls()

        attrs = feature_context.attributes or {}

        return cls(
            account_id=str(attrs.get("account_id", feature_context.target_id or "")),
            strategy_id=str(attrs.get("strategy_id", "")),
            user_id=str(attrs.get("user_id", "")),
            broker=str(attrs.get("broker", "")),
            exchange=str(attrs.get("exchange", "")),
            environment=str(attrs.get("environment", feature_context.environment)),
            account_type=str(attrs.get("account_type", "")),
            tags=frozenset(attrs.get("tags", set())),
            attributes=dict(attrs),
            target_id=feature_context.target_id,
            target_type=feature_context.target_type,
        )

    def get_attribute(self, name: str) -> Any:
        """
        Get an attribute value by name.

        Checks the attributes dict first, then
        falls back to structured fields. This ensures
        that context-specific overrides take precedence
        over default field values.

        Args:
            name: Attribute name.

        Returns:
            Attribute value or None.
        """
        # Check attributes dict first (context-specific values)
        if name in self.attributes:
            return self.attributes[name]

        # Check structured fields
        if hasattr(self, name):
            return getattr(self, name)

        return None

    def has_tag(self, tag: str) -> bool:
        """Check if the context has a specific tag."""
        return tag in self.tags

    def get_numeric(self, name: str) -> Optional[float]:
        """Get an attribute as a numeric value."""
        val = self.get_attribute(name)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> dict:
        """Serialize context to a dictionary."""
        return {
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "user_id": self.user_id,
            "broker": self.broker,
            "exchange": self.exchange,
            "environment": self.environment,
            "account_type": self.account_type,
            "tags": list(self.tags),
            "attributes": self.attributes,
            "target_id": self.target_id,
            "target_type": self.target_type,
        }