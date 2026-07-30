"""Model Router — automatic model selection and routing.

Routes prediction requests to the appropriate model based on symbol,
market, asset class, or custom routing rules. Supports multiple
models serving simultaneously.

Usage::

    router = ModelRouter(config=RouterConfig())
    router.add_rule(RouteRule(market="US", model_name="alpha_us"))
    route = router.route("NVDA", market="US")
    model = route.model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RouteStrategy(str, Enum):
    """Routing strategy."""
    MARKET = "market"
    ASSET_CLASS = "asset_class"
    SYMBOL_PATTERN = "symbol"
    WEIGHTED = "weighted"
    CUSTOM = "custom"


@dataclass
class RouteRule:
    """A routing rule that maps requests to models."""

    market: str = "*"
    asset_class: str = "*"
    symbol_pattern: str = "*"
    model_name: str = ""
    model_version: Optional[str] = None
    priority: int = 0
    weight: float = 1.0
    enabled: bool = True

    def matches(self, symbol: str, market: str = "*", asset_class: str = "*") -> bool:
        if not self.enabled:
            return False
        if self.market != "*" and self.market != market:
            return False
        if self.asset_class != "*" and self.asset_class != asset_class:
            return False
        if self.symbol_pattern != "*":
            import re
            if not re.match(self.symbol_pattern, symbol):
                return False
        return True


@dataclass
class RouteTarget:
    """Result of routing — the selected model."""

    model_name: str
    version: Optional[str] = None
    model: Any = None
    rule: Optional[RouteRule] = None


@dataclass
class RouterConfig:
    """Model router configuration."""

    strategy: RouteStrategy = RouteStrategy.MARKET
    default_model: str = ""
    enable_failover: bool = True
    max_rules: int = 100


class ModelRouter:
    """Routes prediction requests to the appropriate model."""

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        model_loader: Any = None,
    ):
        self.config = config or RouterConfig()
        self._model_loader = model_loader
        self._rules: List[RouteRule] = []
        self._models: Dict[str, Any] = {}
        self._custom_func: Optional[Callable] = None
        self._route_stats: Dict[str, int] = {}

    def add_rule(self, rule: RouteRule) -> None:
        if len(self._rules) >= self.config.max_rules:
            raise ValueError(f"Max {self.config.max_rules} rules reached")
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, model_name: str) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.model_name != model_name]
        return before - len(self._rules)

    def list_rules(self) -> List[RouteRule]:
        return list(self._rules)

    def register_model(self, model_name: str, model: Any) -> None:
        self._models[model_name] = model

    def unregister_model(self, model_name: str) -> bool:
        if model_name in self._models:
            del self._models[model_name]
            return True
        return False

    def get_model(self, model_name: str) -> Optional[RouteTarget]:
        model = self._models.get(model_name)
        if model is not None:
            return RouteTarget(model_name=model_name, model=model)
        if self._model_loader:
            lm = self._model_loader.get(model_name)
            if lm:
                return RouteTarget(model_name=model_name, version=lm.version, model=lm.model)
        return None

    def route(self, symbol: str, market: str = "*", asset_class: str = "*") -> RouteTarget:
        """Route a prediction request to the best matching model."""
        # Try custom function first
        if self.config.strategy == RouteStrategy.CUSTOM and self._custom_func:
            result = self._custom_func(symbol, market, asset_class)
            if result:
                return self._resolve_target(result)

        # Evaluate rules in priority order
        for rule in self._rules:
            if rule.matches(symbol, market, asset_class):
                target = self._resolve_target(rule.model_name, rule)
                if target and target.model is not None:
                    self._route_stats[rule.model_name] = self._route_stats.get(rule.model_name, 0) + 1
                    return target

        # Fallback to default
        if self.config.default_model:
            target = self._resolve_target(self.config.default_model)
            if target:
                return target

        raise ValueError(f"No route found for symbol={symbol} market={market}")

    def set_custom_func(self, func: Callable) -> None:
        """Set a custom routing function."""
        self._custom_func = func

    def get_stats(self) -> Dict[str, int]:
        """Get per-model routing statistics."""
        return dict(self._route_stats)

    # ---- internal ----

    def _resolve_target(self, model_name: str, rule: Optional[RouteRule] = None) -> Optional[RouteTarget]:
        """Resolve model_name to a RouteTarget with loaded model."""
        model = self._models.get(model_name)
        if model is not None:
            return RouteTarget(model_name=model_name, model=model, rule=rule)

        if self._model_loader:
            lm = self._model_loader.get(model_name)
            if lm:
                return RouteTarget(model_name=model_name, version=lm.version, model=lm.model, rule=rule)

            # Try loading
            try:
                lm = self._model_loader.load(model_name)
                return RouteTarget(model_name=model_name, version=lm.version, model=lm.model, rule=rule)
            except Exception:
                pass

        return None
