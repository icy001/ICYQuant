"""Strategy Genome Model – decompose strategies into evolvable DNA."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GenomeComponent:
    """A single component in a strategy genome (e.g., entry rule, filter)."""

    name: str  # e.g. "entry", "filter", "exit", "risk"
    rule_type: str = ""  # e.g. "ma_cross", "volume_filter", "atr_stop"
    params: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0  # relative importance in composite score

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "rule_type": self.rule_type,
            "params": self.params,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenomeComponent":
        return cls(
            name=data.get("name", ""),
            rule_type=data.get("rule_type", ""),
            params=data.get("params", {}),
            weight=data.get("weight", 1.0),
        )


@dataclass
class StrategyGenome:
    """Complete strategy genome – decomposable, mutable, crossable.

    A StrategyGenome represents a strategy as a collection of evolvable
    components (entry, filters, exit, risk management). This abstraction
    enables genetic algorithms: mutation, crossover, and selection to
    automatically discover and optimize strategies.
    """

    name: str
    description: str = ""

    # Core genome components
    entry: GenomeComponent = field(default_factory=lambda: GenomeComponent(name="entry"))
    filters: List[GenomeComponent] = field(default_factory=list)
    exit: GenomeComponent = field(default_factory=lambda: GenomeComponent(name="exit"))
    risk: GenomeComponent = field(default_factory=lambda: GenomeComponent(name="risk"))

    # Metadata
    generation: int = 0  # which evolution generation
    parent_ids: List[str] = field(default_factory=list)  # lineage tracking
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_components(self) -> List[GenomeComponent]:
        """Return all components as a flat list."""
        components = [self.entry, self.exit, self.risk]
        components.extend(self.filters)
        return components

    def get_component(self, name: str) -> Optional[GenomeComponent]:
        """Get a component by name."""
        if name == "entry":
            return self.entry
        if name == "exit":
            return self.exit
        if name == "risk":
            return self.risk
        for f in self.filters:
            if f.name == name:
                return f
        return None

    def add_filter(self, component: GenomeComponent) -> None:
        """Add a filter component to the genome."""
        self.filters.append(component)

    def remove_filter(self, name: str) -> bool:
        """Remove a filter by name. Returns True if removed."""
        for i, f in enumerate(self.filters):
            if f.name == name:
                self.filters.pop(i)
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "entry": self.entry.to_dict(),
            "filters": [f.to_dict() for f in self.filters],
            "exit": self.exit.to_dict(),
            "risk": self.risk.to_dict(),
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def to_rules_dict(self) -> dict:
        """Export genome as a simple rules dictionary for strategy execution."""
        rules: Dict[str, Any] = {
            "entry": {
                "type": self.entry.rule_type,
                "params": self.entry.params,
            },
            "exit": {
                "type": self.exit.rule_type,
                "params": self.exit.params,
            },
            "risk": {
                "type": self.risk.rule_type,
                "params": self.risk.params,
            },
            "filters": [
                {"name": f.name, "type": f.rule_type, "params": f.params}
                for f in self.filters
            ],
        }
        return rules

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyGenome":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            entry=GenomeComponent.from_dict(data.get("entry", {})),
            filters=[GenomeComponent.from_dict(f) for f in data.get("filters", [])],
            exit=GenomeComponent.from_dict(data.get("exit", {})),
            risk=GenomeComponent.from_dict(data.get("risk", {})),
            generation=data.get("generation", 0),
            parent_ids=data.get("parent_ids", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def create_momentum_template(cls) -> "StrategyGenome":
        """Create a momentum strategy genome template."""
        return cls(
            name="Momentum Alpha",
            description="Classic momentum strategy with MA crossover entry",
            entry=GenomeComponent(
                name="entry",
                rule_type="ma_cross",
                params={"fast_period": 20, "slow_period": 50},
            ),
            filters=[
                GenomeComponent(
                    name="volume_filter",
                    rule_type="volume",
                    params={"min_volume_ratio": 1.5},
                ),
            ],
            exit=GenomeComponent(
                name="exit",
                rule_type="atr_stop",
                params={"atr_multiple": 2.0},
            ),
            risk=GenomeComponent(
                name="risk",
                rule_type="fixed_pct",
                params={"max_risk_pct": 2.0},
            ),
            tags=["momentum", "trend_following"],
        )

    @classmethod
    def create_mean_reversion_template(cls) -> "StrategyGenome":
        """Create a mean reversion strategy genome template."""
        return cls(
            name="Mean Reversion",
            description="Mean reversion strategy with Bollinger Band entry",
            entry=GenomeComponent(
                name="entry",
                rule_type="bollinger_band",
                params={"period": 20, "std_dev": 2.0},
            ),
            filters=[
                GenomeComponent(
                    name="rsi_filter",
                    rule_type="rsi",
                    params={"oversold": 30, "overbought": 70},
                ),
            ],
            exit=GenomeComponent(
                name="exit",
                rule_type="mean_return",
                params={"target_std": 0.5},
            ),
            risk=GenomeComponent(
                name="risk",
                rule_type="fixed_pct",
                params={"max_risk_pct": 1.5},
            ),
            tags=["mean_reversion", "contrarian"],
        )

    @classmethod
    def create_breakout_template(cls) -> "StrategyGenome":
        """Create a breakout strategy genome template."""
        return cls(
            name="Breakout Alpha",
            description="Breakout strategy with price channel entry",
            entry=GenomeComponent(
                name="entry",
                rule_type="price_channel",
                params={"lookback": 20, "breakout_pct": 0.02},
            ),
            filters=[
                GenomeComponent(
                    name="volatility_filter",
                    rule_type="atr",
                    params={"min_atr_pct": 1.0},
                ),
            ],
            exit=GenomeComponent(
                name="exit",
                rule_type="trailing_stop",
                params={"trail_pct": 5.0},
            ),
            risk=GenomeComponent(
                name="risk",
                rule_type="volatility_adj",
                params={"base_risk_pct": 2.0},
            ),
            tags=["breakout", "momentum"],
        )
