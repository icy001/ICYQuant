"""
ICYQuant Version Router — Version-aware request dispatching.

Routes requests to the correct model version based on:
  - Context (backtest vs live trading)
  - Version pinning for reproducibility
  - Time-travel requests (historical date → version active at that time)
  - Alias-based routing

This is essential for ensuring backtests can faithfully reproduce
predictions that would have been made at any point in the past.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .model_resolver import ModelResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class RoutingContext(str, Enum):
    """Context in which a model is being called."""
    LIVE_TRADING = "live_trading"
    BACKTEST = "backtest"
    RESEARCH = "research"
    PAPER_TRADING = "paper_trading"
    STRESS_TEST = "stress_test"


@dataclass
class VersionRoute:
    """Resolved version route."""
    model_id: str
    version: str
    context: RoutingContext
    is_pinned: bool = False
    was_alias: bool = False
    original_ref: str = ""
    resolved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "context": self.context.value,
            "is_pinned": self.is_pinned,
            "was_alias": self.was_alias,
            "original_ref": self.original_ref,
            "resolved_at": self.resolved_at,
        }


@dataclass
class VersionTimeline:
    """Records when each model version was active.

    Used for time-travel queries: "what version was serving on 2025-03-15?"
    """
    model_id: str
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add_entry(self, version: str, active_from: str, active_to: Optional[str] = None) -> None:
        self.entries.append({
            "version": version,
            "active_from": active_from,
            "active_to": active_to,
        })

    def get_version_at(self, target_date: str) -> Optional[str]:
        """Get the version that was active at a given date."""
        target = datetime.fromisoformat(target_date)

        for entry in sorted(self.entries, key=lambda e: e["active_from"]):
            active_from = datetime.fromisoformat(entry["active_from"])
            if target < active_from:
                continue
            if entry["active_to"]:
                active_to = datetime.fromisoformat(entry["active_to"])
                if target > active_to:
                    continue
            return entry["version"]

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "entries": self.entries,
        }


# ---------------------------------------------------------------------------
# Version Router
# ---------------------------------------------------------------------------

class VersionRouter:
    """Version-aware intelligent request dispatching.

    Key features:
      - Context-based version selection (live vs backtest)
      - Time-travel queries for historical reproducibility
      - Alias resolution
      - Version pinning with validation
      - Version timeline tracking

    Usage::

        router = VersionRouter(resolver)
        route = await router.resolve("nvda_alpha_model", context=RoutingContext.LIVE_TRADING)
        route = await router.resolve_at("nvda_alpha_model", date="2025-06-15")
    """

    def __init__(self, resolver: "ModelResolver"):
        self.resolver = resolver
        self._initialized = False
        self._timelines: Dict[str, VersionTimeline] = {}

        # Context → default version strategy
        self._context_strategies: Dict[RoutingContext, str] = {
            RoutingContext.LIVE_TRADING: "production",
            RoutingContext.BACKTEST: "pinned",
            RoutingContext.RESEARCH: "latest",
            RoutingContext.PAPER_TRADING: "staging",
            RoutingContext.STRESS_TEST: "production",
        }

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("VersionRouter initialized")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        model_ref: str,
        *,
        context: RoutingContext = RoutingContext.LIVE_TRADING,
        pinned_version: Optional[str] = None,
    ) -> VersionRoute:
        """Resolve which version to use based on context.

        Rules:
          - LIVE_TRADING → production version
          - BACKTEST → pinned version (EXACT, no auto-upgrade)
          - RESEARCH → latest version
          - Explicit pin always wins over context

        Args:
            model_ref: Model identifier (may include ':version').
            context: Request context.
            pinned_version: Override version explicitly.

        Returns:
            VersionRoute with resolved version.
        """
        from .model_resolver import ResolutionStrategy

        # Parse explicit version from model_ref
        model_id = model_ref
        explicit_version = None
        if ":" in model_ref:
            parts = model_ref.rsplit(":", 1)
            model_id = parts[0]
            explicit_version = parts[1]

        # Resolve alias
        resolved_id = self.resolver.resolve_alias(model_id) or model_id
        was_alias = resolved_id != model_id

        # Explicit version (pinned) wins
        if explicit_version:
            return VersionRoute(
                model_id=resolved_id,
                version=explicit_version,
                context=context,
                is_pinned=True,
                was_alias=was_alias,
                original_ref=model_ref,
            )

        if pinned_version:
            return VersionRoute(
                model_id=resolved_id,
                version=pinned_version,
                context=context,
                is_pinned=True,
                was_alias=was_alias,
                original_ref=model_ref,
            )

        # Context-based strategy
        strategy_name = self._context_strategies.get(context, "production")
        strategy = ResolutionStrategy(strategy_name)

        try:
            result = await self.resolver.resolve(
                resolved_id,
                strategy=strategy,
            )
        except ValueError:
            # Fallback to latest
            result = await self.resolver.resolve(
                resolved_id,
                strategy=ResolutionStrategy.LATEST,
            )

        return VersionRoute(
            model_id=result.model_id,
            version=result.version,
            context=context,
            is_pinned=False,
            was_alias=was_alias,
            original_ref=model_ref,
            metadata=result.metadata,
        )

    async def resolve_at(
        self,
        model_id: str,
        date: str,
        context: RoutingContext = RoutingContext.BACKTEST,
    ) -> VersionRoute:
        """Time-travel: resolve version active at a specific historical date.

        This is critical for backtesting — ensures we use the exact model
        version that would have been serving at that point in time.

        Args:
            model_id: Model identifier.
            date: ISO date string (e.g. '2025-06-15').
            context: Request context (typically BACKTEST).

        Returns:
            VersionRoute for the historical version.
        """
        # Check timeline first
        timeline = self._timelines.get(model_id)
        if timeline:
            version = timeline.get_version_at(date)
            if version:
                return VersionRoute(
                    model_id=model_id,
                    version=version,
                    context=context,
                    is_pinned=True,
                    original_ref=f"{model_id}@{date}",
                    metadata={"historical_date": date},
                )

        # Fallback: resolve as normal (backtest context goes to production)
        route = await self.resolve(model_id, context=context)
        route.metadata["historical_date"] = date
        route.metadata["historical_resolution"] = "fallback_to_registry"
        return route

    async def resolve_batch(
        self,
        model_refs: List[str],
        context: RoutingContext = RoutingContext.LIVE_TRADING,
    ) -> Dict[str, VersionRoute]:
        """Resolve multiple model references in batch."""
        tasks = [
            self.resolve(ref, context=context)
            for ref in model_refs
        ]
        routes = await asyncio.gather(*tasks)
        return {r.original_ref or r.model_id: r for r in routes}

    # ------------------------------------------------------------------
    # Timeline management
    # ------------------------------------------------------------------

    def record_deployment(
        self,
        model_id: str,
        version: str,
        deployed_at: Optional[str] = None,
    ) -> None:
        """Record that a version was deployed at a specific time.

        This builds the version timeline for time-travel queries.

        Args:
            model_id: Model identifier.
            version: Deployed version.
            deployed_at: ISO datetime of deployment (default: now).
        """
        if model_id not in self._timelines:
            self._timelines[model_id] = VersionTimeline(model_id=model_id)

        deployed_time = deployed_at or datetime.now(timezone.utc).isoformat()
        timeline = self._timelines[model_id]

        # Close previous entry
        if timeline.entries:
            timeline.entries[-1]["active_to"] = deployed_time

        timeline.add_entry(
            version=version,
            active_from=deployed_time,
        )

        logger.info(
            "Timeline recorded: %s@%s deployed at %s",
            model_id, version, deployed_time,
        )

    def get_timeline(self, model_id: str) -> Optional[VersionTimeline]:
        """Get version timeline for a model."""
        return self._timelines.get(model_id)

    def list_timelines(self) -> Dict[str, VersionTimeline]:
        """List all version timelines."""
        return dict(self._timelines)

    # ------------------------------------------------------------------
    # Context configuration
    # ------------------------------------------------------------------

    def set_context_strategy(self, context: RoutingContext, strategy: str) -> None:
        """Set the default version strategy for a context."""
        self._context_strategies[context] = strategy
        logger.info("Context strategy: %s → %s", context.value, strategy)

    def get_context_strategy(self, context: RoutingContext) -> str:
        return self._context_strategies.get(context, "production")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_version(
        self,
        model_id: str,
        version: str,
    ) -> bool:
        """Check if a version exists and is loadable."""
        try:
            result = await self.resolver.resolve(f"{model_id}:{version}")
            return result.artifact_path is not None
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "timelines_tracked": len(self._timelines),
            "contexts_configured": len(self._context_strategies),
        }

    def __repr__(self) -> str:
        return f"VersionRouter(timelines={len(self._timelines)})"
