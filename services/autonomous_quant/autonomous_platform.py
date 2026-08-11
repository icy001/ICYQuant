"""Autonomous Platform — Top-level orchestrator for autonomous quant research.

The AutonomousPlatform is the entry point for the self-driving research system.
It coordinates Market Scanning → Opportunity Detection → Hypothesis Generation →
Factor Mining → Alpha Discovery → Strategy Generation within defined autonomy
boundaries enforced by policy, compute budget, and risk guards.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .autonomy_runtime import AutonomyRuntime
from .autonomy_manager import AutonomyManager
from .autonomy_controller import AutonomyController
from .autonomy_gateway import AutonomyGateway
from .autonomy_orchestrator import AutonomyOrchestrator
from .autonomy_policy import AutonomyPolicy
from .budget_controller import BudgetController
from .risk_guard import RiskGuard
from .candidate_registry import CandidateRegistry
from .discovery_memory import DiscoveryMemory

logger = logging.getLogger(__name__)


class AutonomyLevel(Enum):
    """Autonomy levels — controls how independently the system operates."""

    LEVEL_0_MANUAL = 0
    LEVEL_1_SUGGEST = 1
    LEVEL_2_EXPERIMENT = 2
    LEVEL_3_CANDIDATE = 3
    LEVEL_4_VALIDATE = 4
    LEVEL_5_PROPOSE = 5


class PlatformStatus(Enum):
    """Platform operational status."""

    INITIALIZING = "initializing"
    SCANNING = "scanning"
    DISCOVERING = "discovering"
    IDLE = "idle"
    PAUSED = "paused"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    OFFLINE = "offline"


@dataclass
class AutonomyConfig:
    """Configuration for autonomous quant platform."""

    level: AutonomyLevel = AutonomyLevel.LEVEL_2_EXPERIMENT
    scan_interval_seconds: float = 300.0
    max_concurrent_research: int = 10
    max_daily_hypotheses: int = 100
    max_daily_experiments: int = 50
    max_daily_backtests: int = 500
    require_approval_above_level: AutonomyLevel = AutonomyLevel.LEVEL_3_CANDIDATE
    enable_auto_factor_discovery: bool = True
    enable_auto_alpha_discovery: bool = True
    enable_auto_strategy_generation: bool = False
    enable_discovery_memory: bool = True


class AutonomousPlatform:
    """Autonomous Quant Platform — self-driving research and discovery.

    Architecture:
        Market Data → Scanner → Opportunity → Hypothesis → Research →
        Factor Mining → Alpha Discovery → Strategy Generation →
        Backtesting → Validation → Candidate Registry → Memory

    Safety boundaries:
        - Autonomy level caps operational scope
        - Compute budget prevents runaway consumption
        - Risk guard filters strategy candidates
        - Approval gate for production proposals
        - Discovery memory prevents repeating failures
    """

    def __init__(self, config: Optional[AutonomyConfig] = None) -> None:
        self.config = config or AutonomyConfig()
        self.status = PlatformStatus.INITIALIZING
        self._start_time: Optional[datetime] = None

        # Subsystems
        self.runtime = AutonomyRuntime()
        self.manager = AutonomyManager(self.config)
        self.controller = AutonomyController(self.config)
        self.gateway = AutonomyGateway(self.config)
        self.orchestrator = AutonomyOrchestrator(self.config)
        self.policy = AutonomyPolicy(self.config)
        self.budget = BudgetController(self.config)
        self.risk_guard = RiskGuard(self.config)
        self.registry = CandidateRegistry()
        self.memory = DiscoveryMemory() if self.config.enable_discovery_memory else None

        # Statistics
        self._cycles_completed: int = 0
        self._opportunities_detected: int = 0
        self._hypotheses_generated: int = 0
        self._factors_discovered: int = 0
        self._alphas_discovered: int = 0
        self._strategies_generated: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the autonomous quant platform."""
        self.status = PlatformStatus.INITIALIZING
        self._start_time = datetime.now(timezone.utc)
        logger.info("Autonomous Quant starting (level=%s)", self.config.level.name)

        await self.runtime.start()
        await self.manager.start()
        await self.controller.start()
        await self.gateway.start()
        await self.orchestrator.start()

        if self.memory:
            await self.memory.start()

        self.status = PlatformStatus.IDLE
        logger.info("Autonomous Quant ready")

    async def stop(self) -> None:
        """Stop the autonomous quant platform."""
        self.status = PlatformStatus.SHUTTING_DOWN
        logger.info("Autonomous Quant shutting down")

        for name, sub in [
            ("Orchestrator", self.orchestrator),
            ("Gateway", self.gateway),
            ("Controller", self.controller),
            ("Manager", self.manager),
            ("Runtime", self.runtime),
        ]:
            try:
                await sub.stop()
            except Exception as exc:
                logger.warning("Error stopping %s: %s", name, exc)

        if self.memory:
            await self.memory.stop()

        self.status = PlatformStatus.OFFLINE
        logger.info("Autonomous Quant offline")

    # ------------------------------------------------------------------
    # Research Cycle
    # ------------------------------------------------------------------

    async def run_research_cycle(self) -> Dict[str, Any]:
        """Run one complete autonomous research cycle.

        Scan → Discover → Hypothesize → Research → Mine → Validate → Record

        Returns:
            Dict with cycle results summary.
        """
        if self.status not in (PlatformStatus.IDLE, PlatformStatus.SCANNING):
            logger.warning("Cannot run cycle: platform status=%s", self.status.value)
            return {"status": "skipped", "reason": self.status.value}

        self.status = PlatformStatus.SCANNING
        cycle_id = f"arc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        cycle_start = datetime.now(timezone.utc)

        try:
            # Budget check
            if not await self.budget.can_run_cycle():
                return {"status": "budget_exceeded", "cycle_id": cycle_id}

            results = await self.orchestrator.run_cycle()

            # Record to registry and memory
            await self._record_cycle_results(cycle_id, results)

            self._cycles_completed += 1
            self._opportunities_detected += results.get("opportunities_found", 0)
            self._hypotheses_generated += results.get("hypotheses_generated", 0)
            self._factors_discovered += results.get("factors_found", 0)
            self._alphas_discovered += results.get("alphas_found", 0)
            self._strategies_generated += results.get("strategies_generated", 0)

            return {
                "status": "completed",
                "cycle_id": cycle_id,
                **results,
            }

        except Exception as exc:
            logger.error("Research cycle failed: %s", exc, exc_info=True)
            return {"status": "error", "cycle_id": cycle_id, "error": str(exc)}

        finally:
            self.status = PlatformStatus.IDLE

    async def run_continuous(self) -> None:
        """Run continuous autonomous research loop."""
        logger.info("Starting continuous autonomous research loop")
        self.status = PlatformStatus.SCANNING

        while self.status == PlatformStatus.SCANNING:
            try:
                await self.run_research_cycle()
                await asyncio.sleep(self.config.scan_interval_seconds)
            except Exception as exc:
                logger.error("Continuous cycle error: %s", exc)
                await asyncio.sleep(60)  # Back off on error

    # ------------------------------------------------------------------
    # Quick Access
    # ------------------------------------------------------------------

    async def scan_market(self) -> List[Dict[str, Any]]:
        """Quick market scan for opportunities."""
        return await self.orchestrator.scan()

    async def discover_alpha(self, hypothesis_id: str) -> Dict[str, Any]:
        """Discover alpha for a specific hypothesis."""
        return await self.orchestrator.discover_alpha(hypothesis_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _record_cycle_results(
        self,
        cycle_id: str,
        results: Dict[str, Any],
    ) -> None:
        """Record cycle results to registry and memory."""
        # Record to registry
        for candidate in results.get("candidates", []):
            await self.registry.register(candidate)

        # Record to discovery memory
        if self.memory:
            await self.memory.record_cycle(cycle_id, results)

    # ------------------------------------------------------------------
    # Health & Metrics
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Platform health status."""
        return {
            "status": self.status.value,
            "autonomy_level": self.config.level.name,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "cycles_completed": self._cycles_completed,
            "opportunities_detected": self._opportunities_detected,
            "hypotheses_generated": self._hypotheses_generated,
            "factors_discovered": self._factors_discovered,
            "alphas_discovered": self._alphas_discovered,
            "strategies_generated": self._strategies_generated,
            "subsystems": {
                "runtime": await self.runtime.health(),
                "manager": await self.manager.health(),
                "controller": await self.controller.health(),
                "gateway": await self.gateway.health(),
                "orchestrator": await self.orchestrator.health(),
                "budget": await self.budget.health(),
                "registry": await self.registry.health(),
            },
        }

    async def metrics(self) -> Dict[str, Any]:
        """Platform metrics."""
        return {
            "icyquant_autonomous_research_tasks_total": self._cycles_completed,
            "icyquant_opportunities_detected_total": self._opportunities_detected,
            "icyquant_hypotheses_generated_total": self._hypotheses_generated,
            "icyquant_factors_discovered_total": self._factors_discovered,
            "icyquant_alpha_candidates_total": self._alphas_discovered,
            "icyquant_strategy_candidates_total": self._strategies_generated,
        }
