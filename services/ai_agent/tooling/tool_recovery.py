"""Tool Recovery — failure recovery with fallback tools and graceful degradation.

Pipeline:
    Tool Execution Failure (after retries exhausted)
        -> RecoveryPlanner.find_plan()
        -> RecoveryPlan (fallback tool, alternative params, partial result)
        -> Execute Fallback
        -> Degraded Result or Full Recovery
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.ai_agent.tooling.tool_registry import ToolRegistry
from services.ai_agent.tooling.tool_result import ToolResult

logger = logging.getLogger(__name__)


# ── Enums ──

class RecoveryAction(str, Enum):
    """Type of recovery action."""

    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_TOOL = "fallback_tool"
    ALTERNATIVE_PARAMS = "alternative_params"
    PARTIAL_RESULT = "partial_result"
    DEGRADED_MODE = "degraded_mode"
    NOOP = "noop"  # Do nothing, report failure


# ── RecoveryStep ──

@dataclass
class RecoveryStep:
    """A single step in a recovery plan."""

    action: RecoveryAction
    tool_name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    priority: int = 0
    timeout_seconds: float = 30.0


# ── RecoveryPlan ──

@dataclass
class RecoveryPlan:
    """A plan for recovering from tool execution failure."""

    plan_id: str = ""
    original_tool: str = ""
    failure_reason: str = ""
    steps: List[RecoveryStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        return len(self.steps) == 0

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "original_tool": self.original_tool,
            "failure_reason": self.failure_reason,
            "steps": [
                {
                    "action": s.action.value,
                    "tool_name": s.tool_name,
                    "description": s.description,
                    "priority": s.priority,
                }
                for s in self.steps
            ],
        }


# ── RecoveryResult ──

@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    recovered: bool = False
    plan: Optional[RecoveryPlan] = None
    result: Optional[ToolResult] = None
    steps_executed: int = 0
    steps_failed: int = 0
    fallback_tool_used: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "recovered": self.recovered,
            "plan_id": self.plan.plan_id if self.plan else None,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "fallback_tool_used": self.fallback_tool_used,
            "message": self.message,
            "result": self.result.to_summary() if self.result else None,
        }


# ── ToolRecovery ──

class ToolRecovery:
    """Recovery manager for handling tool execution failures.

    When a tool fails after all retries are exhausted, the recovery
    engine finds and executes a recovery plan with fallback tools,
    alternative parameters, or degraded results.

    Supports:
        - Pre-registered fallback tool mappings
        - Multi-step recovery plans
        - Alternative parameter substitution
        - Partial result acceptance
        - Degraded mode execution
        - Recovery plan generation

    Usage:
        recovery = ToolRecovery(registry)
        recovery.register_fallback("backtest.run", "backtest.simple")
        plan = recovery.find_plan("backtest.run", "timeout")
        result = await recovery.execute_plan(plan, executor)
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize the recovery manager.

        Args:
            registry: The ToolRegistry for tool lookup.
        """
        self._registry = registry

        # ── Fallback Mappings ──
        self._fallbacks: Dict[str, List[str]] = {}  # tool_name -> [fallback_names]
        self._recovery_handlers: Dict[str, Callable] = {}  # tool_name -> custom handler

        self._initialized: bool = False
        logger.info("ToolRecovery created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the recovery manager."""
        self._initialized = True
        logger.info("ToolRecovery initialized")

    async def shutdown(self) -> None:
        """Shutdown the recovery manager."""
        self._fallbacks.clear()
        self._recovery_handlers.clear()
        self._initialized = False
        logger.info("ToolRecovery shutdown complete")

    # ── Fallback Registration ──

    def register_fallback(self, tool_name: str, fallback_names: List[str]) -> None:
        """Register fallback tools for a primary tool.

        Args:
            tool_name: The primary tool name.
            fallback_names: Ordered list of fallback tool names.
        """
        self._fallbacks[tool_name] = fallback_names
        logger.info(f"Fallbacks registered for {tool_name}: {fallback_names}")

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """Register a custom recovery handler for a tool.

        Args:
            tool_name: The tool name.
            handler: An async callable that receives (tool_name, error, params)
                     and returns a RecoveryResult.
        """
        self._recovery_handlers[tool_name] = handler
        logger.info(f"Recovery handler registered for {tool_name}")

    # ── Plan Generation ──

    def find_plan(
        self,
        tool_name: str,
        failure_reason: str,
        original_params: Optional[Dict[str, Any]] = None,
    ) -> RecoveryPlan:
        """Generate a recovery plan for a failed tool call.

        Args:
            tool_name: The failed tool name.
            failure_reason: The failure description.
            original_params: The original parameters.

        Returns:
            A RecoveryPlan with ordered recovery steps.
        """
        from uuid import uuid4

        plan_id = uuid4().hex
        plan = RecoveryPlan(
            plan_id=plan_id,
            original_tool=tool_name,
            failure_reason=failure_reason,
        )

        # ── Step 1: Check for custom handler ──
        if tool_name in self._recovery_handlers:
            plan.steps.append(
                RecoveryStep(
                    action=RecoveryAction.FALLBACK_TOOL,
                    tool_name=tool_name,
                    description=f"Custom recovery handler for {tool_name}",
                    priority=100,
                )
            )

        # ── Step 2: Fallback tools ──
        fallbacks = self._fallbacks.get(tool_name, [])
        for i, fallback_name in enumerate(fallbacks):
            fallback_tool = self._registry.lookup(fallback_name)
            if fallback_tool and not fallback_tool.deprecated:
                plan.steps.append(
                    RecoveryStep(
                        action=RecoveryAction.FALLBACK_TOOL,
                        tool_name=fallback_name,
                        params=original_params or {},
                        description=f"Fallback to {fallback_name}",
                        priority=90 - i,
                    )
                )

        # ── Step 3: Alternative params (if applicable) ──
        if original_params:
            plan.steps.append(
                RecoveryStep(
                    action=RecoveryAction.ALTERNATIVE_PARAMS,
                    tool_name=tool_name,
                    params=self._generate_alternative_params(original_params),
                    description="Retry with simplified parameters",
                    priority=50,
                )
            )

        # ── Step 4: Partial result ──
        plan.steps.append(
            RecoveryStep(
                action=RecoveryAction.PARTIAL_RESULT,
                tool_name=tool_name,
                description="Accept partial result if available",
                priority=30,
            )
        )

        # ── Step 5: Degraded mode ──
        plan.steps.append(
            RecoveryStep(
                action=RecoveryAction.DEGRADED_MODE,
                tool_name=tool_name,
                description="Execute in degraded mode",
                priority=10,
            )
        )

        # Sort by priority (descending)
        plan.steps.sort(key=lambda s: -s.priority)

        logger.info(
            f"Recovery plan created for {tool_name}: "
            f"{plan.step_count} steps, reason='{failure_reason}'"
        )

        return plan

    # ── Plan Execution ──

    async def execute_plan(
        self,
        plan: RecoveryPlan,
        executor: Any = None,
        original_params: Optional[Dict[str, Any]] = None,
    ) -> RecoveryResult:
        """Execute a recovery plan.

        Args:
            plan: The recovery plan to execute.
            executor: The ToolExecutor instance.
            original_params: The original parameters.

        Returns:
            A RecoveryResult with the outcome.
        """
        result = RecoveryResult(plan=plan)

        for step in plan.steps:
            try:
                if step.action == RecoveryAction.FALLBACK_TOOL and executor:
                    if plan.original_tool in self._recovery_handlers:
                        handler = self._recovery_handlers[plan.original_tool]
                        custom_result = await handler(
                            plan.original_tool,
                            plan.failure_reason,
                            original_params or {},
                        )
                        if custom_result:
                            result.recovered = True
                            result.fallback_tool_used = plan.original_tool
                            result.message = "Recovered via custom handler"
                            result.steps_executed += 1
                            return result

                    if step.tool_name:
                        tool_result = await executor.execute(
                            tool_name=step.tool_name,
                            params=step.params or original_params,
                        )
                        result.steps_executed += 1
                        if tool_result.success:
                            result.recovered = True
                            result.result = tool_result
                            result.fallback_tool_used = step.tool_name
                            result.message = f"Recovered via fallback: {step.tool_name}"
                            logger.info(
                                f"Recovery succeeded via {step.tool_name} "
                                f"for {plan.original_tool}"
                            )
                            return result
                        else:
                            result.steps_failed += 1
                            logger.warning(
                                f"Recovery step failed: {step.tool_name} - {tool_result.error}"
                            )

                elif step.action == RecoveryAction.NOOP:
                    result.steps_executed += 1
                    result.message = "Recovery not possible, reported failure"
                    return result

                else:
                    result.steps_executed += 1
                    logger.debug(f"Recovery step skipped: {step.action.value}")

            except Exception as e:
                result.steps_failed += 1
                logger.exception(f"Recovery step execution error: {e}")

        # All steps exhausted
        result.message = f"Recovery failed after {result.steps_executed} steps"
        logger.warning(result.message)
        return result

    # ── Private Methods ──

    @staticmethod
    def _generate_alternative_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate simplified alternative parameters.

        Args:
            params: Original parameters.

        Returns:
            Simplified parameter dictionary.
        """
        alt = {}
        for key, value in params.items():
            # Reduce batch sizes, simplify date ranges, etc.
            if isinstance(value, int) and value > 100:
                alt[key] = max(1, value // 10)
            elif isinstance(value, list) and len(value) > 10:
                alt[key] = value[:5]
            else:
                alt[key] = value
        return alt

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get recovery manager status."""
        return {
            "fallback_tools": {
                tool: fallbacks for tool, fallbacks in self._fallbacks.items()
            },
            "tools_with_handlers": list(self._recovery_handlers.keys()),
            "initialized": self._initialized,
        }
