"""
Scenario Repository — Persistent storage and lifecycle management for risk scenarios.

Provides CRUD operations, versioning, and persistence for scenario definitions.
Acts as the single source of truth for scenario data across the analytics platform.
"""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional

from .scenario_library import Scenario, ScenarioLibrary

logger = logging.getLogger(__name__)


class ScenarioRepository:
    """
    Persistent storage and lifecycle management for risk scenarios.

    Features:
    - CRUD operations for scenarios
    - Version tracking and change history
    - In-memory caching with optional persistence backend
    - Bulk import/export
    - Scenario lifecycle states (draft, active, deprecated, archived)

    Usage::

        repo = ScenarioRepository()
        await repo.initialize()
        scenario = await repo.get("2008_gfc")
        await repo.activate("2008_gfc")
    """

    def __init__(
        self,
        library: Optional[ScenarioLibrary] = None,
        persistence_backend: Optional[Any] = None,
    ) -> None:
        self._library = library or ScenarioLibrary()
        self._backend = persistence_backend
        self._versions: dict[str, list[dict]] = {}
        self._state: dict[str, str] = {}  # scenario_id -> lifecycle state
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the repository."""
        if self._initialized:
            return
        self._library.initialize()
        # All built-in scenarios start as 'active'
        for s in self._library.get_all():
            self._state[s.scenario_id] = "active"
        self._initialized = True
        logger.info(f"ScenarioRepository initialized with {self.count()} scenarios.")

    # ---- CRUD ----

    async def get(self, scenario_id: str) -> Optional[Scenario]:
        """Get a scenario by ID."""
        return self._library.get(scenario_id)

    async def get_by_ids(self, scenario_ids: list[str]) -> list[Scenario]:
        """Get multiple scenarios by IDs."""
        return [s for sid in scenario_ids if (s := self._library.get(sid)) is not None]

    async def get_all(self) -> list[Scenario]:
        """Get all scenarios."""
        return self._library.get_all()

    async def get_active(self) -> list[Scenario]:
        """Get all active scenarios."""
        return [s for s in self._library.get_all() if self._state.get(s.scenario_id) == "active"]

    async def create(self, scenario: Scenario) -> Scenario:
        """Create a new custom scenario."""
        self._library.add_custom(scenario)
        self._state[scenario.scenario_id] = "draft"
        self._record_version(scenario.scenario_id, scenario, "created")
        logger.info(f"ScenarioRepository: created scenario '{scenario.scenario_id}'.")
        return scenario

    async def update(self, scenario: Scenario) -> Optional[Scenario]:
        """Update an existing scenario (custom only)."""
        existing = self._library.get(scenario.scenario_id)
        if existing is None:
            logger.warning(f"Scenario '{scenario.scenario_id}' not found for update.")
            return None
        self._library.update_custom(scenario)
        self._record_version(scenario.scenario_id, scenario, "updated")
        logger.info(f"ScenarioRepository: updated scenario '{scenario.scenario_id}'.")
        return scenario

    async def delete(self, scenario_id: str) -> bool:
        """Delete a custom scenario."""
        if self._state.get(scenario_id) == "builtin":
            logger.warning(f"Cannot delete built-in scenario '{scenario_id}'.")
            return False
        removed = self._library.remove_custom(scenario_id)
        if removed:
            self._state.pop(scenario_id, None)
            self._versions.pop(scenario_id, None)
        return removed

    # ---- Lifecycle ----

    async def activate(self, scenario_id: str) -> bool:
        """Activate a scenario for use in stress tests."""
        if scenario_id not in self._state:
            return False
        self._state[scenario_id] = "active"
        return True

    async def deactivate(self, scenario_id: str) -> bool:
        """Deactivate a scenario."""
        if scenario_id not in self._state:
            return False
        self._state[scenario_id] = "inactive"
        return True

    async def deprecate(self, scenario_id: str) -> bool:
        """Mark a scenario as deprecated."""
        if scenario_id not in self._state:
            return False
        self._state[scenario_id] = "deprecated"
        return True

    async def archive(self, scenario_id: str) -> bool:
        """Archive a scenario."""
        if scenario_id not in self._state:
            return False
        self._state[scenario_id] = "archived"
        return True

    # ---- Version History ----

    async def get_versions(self, scenario_id: str) -> list[dict]:
        """Get version history for a scenario."""
        return self._versions.get(scenario_id, [])

    # ---- Bulk Operations ----

    async def export_scenarios(self, scenario_ids: Optional[list[str]] = None) -> dict[str, Any]:
        """Export scenarios as JSON-serializable dict."""
        scenarios = (
            self.get_by_ids(scenario_ids)
            if scenario_ids
            else self._library.get_all()
        )
        data = {}
        for s in await scenarios if asyncio.iscoroutine(scenarios) else scenarios:
            data[s.scenario_id] = {
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "severity": s.severity,
                "asset_shocks": s.asset_shocks,
                "macro_variables": s.macro_variables,
                "volatility_multiplier": s.volatility_multiplier,
                "liquidity_discount": s.liquidity_discount,
                "tags": s.tags,
            }
        return {"scenarios": data, "exported_at": datetime.now(timezone.utc).isoformat()}

    async def import_scenarios(self, data: dict[str, Any]) -> int:
        """Import scenarios from dict."""
        imported = 0
        for sid, sdata in data.get("scenarios", {}).items():
            scenario = Scenario(
                scenario_id=sid,
                name=sdata.get("name", sid),
                description=sdata.get("description", ""),
                category=sdata.get("category", "custom"),
                severity=sdata.get("severity", "moderate"),
                asset_shocks=sdata.get("asset_shocks", {}),
                macro_variables=sdata.get("macro_variables", {}),
                volatility_multiplier=sdata.get("volatility_multiplier", 1.0),
                liquidity_discount=sdata.get("liquidity_discount", 0.0),
                tags=sdata.get("tags", []),
            )
            await self.create(scenario)
            imported += 1
        logger.info(f"ScenarioRepository: imported {imported} scenarios.")
        return imported

    # ---- Stats ----

    async def count(self) -> int:
        """Total scenario count."""
        return self._library.count()

    async def count_by_state(self) -> dict[str, int]:
        """Count scenarios by lifecycle state."""
        counts: dict[str, int] = {}
        for state in self._state.values():
            counts[state] = counts.get(state, 0) + 1
        return counts

    # ---- Internal ----

    def _record_version(self, scenario_id: str, scenario: Scenario, action: str) -> None:
        """Record a version snapshot."""
        if scenario_id not in self._versions:
            self._versions[scenario_id] = []
        self._versions[scenario_id].append({
            "scenario_id": scenario_id,
            "name": scenario.name,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shocks_snapshot": deepcopy(scenario.asset_shocks),
        })
        # Keep only last 50 versions
        if len(self._versions[scenario_id]) > 50:
            self._versions[scenario_id] = self._versions[scenario_id][-50:]
