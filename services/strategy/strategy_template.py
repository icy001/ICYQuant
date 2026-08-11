"""
Strategy templates for rapid strategy creation.

Provides pre-configured strategy blueprints with standard patterns
for common strategy types (trend, mean reversion, arbitrage, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .strategy_manifest import StrategyEntryPoint, StrategyManifest
from .strategy_metadata import StrategyCapability

logger = logging.getLogger(__name__)


class TemplateCategory(str, Enum):
    """Categories of strategy templates."""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    PAIRS_TRADING = "pairs_trading"
    STAT_ARBITRAGE = "stat_arbitrage"
    EVENT_DRIVEN = "event_driven"
    SENTIMENT = "sentiment"
    ML_BASED = "ml_based"
    CUSTOM = "custom"


@dataclass
class StrategyTemplate:
    """Blueprint for creating a new strategy."""

    template_id: str
    name: str
    description: str
    category: TemplateCategory = TemplateCategory.CUSTOM

    # Default manifest values
    default_capability: StrategyCapability = field(default_factory=StrategyCapability)
    default_entry_point: StrategyEntryPoint = field(default_factory=StrategyEntryPoint)

    # Schema
    config_schema: Dict[str, Any] = field(default_factory=dict)
    required_config_fields: List[str] = field(default_factory=list)

    # Code skeleton
    code_skeleton: str = ""
    test_skeleton: str = ""

    # Metadata
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "icyquant"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deprecated: bool = False

    def create_manifest(
        self,
        strategy_name: str,
        version: str = "0.1.0",
        author: str = "unknown",
        **overrides: Any,
    ) -> StrategyManifest:
        """Create a manifest from this template."""
        manifest_data = {
            "name": strategy_name,
            "version": version,
            "author": author,
            "description": self.description,
            "capability": self.default_capability.to_dict(),
            "entry_point": self.default_entry_point.to_dict(),
            "config_schema": self.config_schema,
            "tags": list(self.tags),
            **overrides,
        }
        return StrategyManifest.from_dict(manifest_data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "capability": self.default_capability.to_dict(),
            "config_schema": self.config_schema,
            "required_config_fields": self.required_config_fields,
            "tags": self.tags,
            "version": self.version,
            "author": self.author,
            "deprecated": self.deprecated,
        }


# ── Built-in Templates ──

BUILT_IN_TEMPLATES: List[StrategyTemplate] = [
    StrategyTemplate(
        template_id="trend_following_basic",
        name="Basic Trend Following",
        description="A simple moving-average crossover trend following strategy.",
        category=TemplateCategory.TREND_FOLLOWING,
        default_capability=StrategyCapability(
            asset_classes=["equity"],
            markets=["CN"],
            frequency="daily",
            style="trend",
            long_only=True,
        ),
        tags=["trend", "moving_average", "beginner"],
        config_schema={
            "type": "object",
            "properties": {
                "fast_period": {"type": "integer", "default": 5},
                "slow_period": {"type": "integer", "default": 20},
            },
        },
        required_config_fields=["fast_period", "slow_period"],
    ),
    StrategyTemplate(
        template_id="mean_reversion_basic",
        name="Basic Mean Reversion",
        description="A Bollinger Bands mean reversion strategy.",
        category=TemplateCategory.MEAN_REVERSION,
        default_capability=StrategyCapability(
            asset_classes=["equity"],
            markets=["CN"],
            frequency="daily",
            style="mean_reversion",
            long_only=True,
        ),
        tags=["mean_reversion", "bollinger", "beginner"],
        config_schema={
            "type": "object",
            "properties": {
                "period": {"type": "integer", "default": 20},
                "std_dev": {"type": "number", "default": 2.0},
            },
        },
        required_config_fields=["period", "std_dev"],
    ),
    StrategyTemplate(
        template_id="momentum_basic",
        name="Basic Momentum",
        description="A price momentum strategy with lookback period.",
        category=TemplateCategory.MOMENTUM,
        default_capability=StrategyCapability(
            asset_classes=["equity"],
            markets=["CN", "US"],
            frequency="daily",
            style="momentum",
            long_only=True,
        ),
        tags=["momentum", "intermediate"],
        config_schema={
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "default": 60},
                "top_n": {"type": "integer", "default": 10},
            },
        },
        required_config_fields=["lookback_days", "top_n"],
    ),
]
