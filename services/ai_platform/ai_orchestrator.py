"""AI Orchestrator — Coordinates AI subsystems into unified workflows.

The orchestrator composes Research, Agents, Features, Models, Strategy,
Risk, and Portfolio into end-to-end intelligence pipelines.

It is the central coordination layer that sequences AI operations
without each subsystem knowing about the others.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .ai_context import AIContext
from .ai_session import AISession

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationStep:
    """A single step in an orchestrated workflow."""

    name: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationTrace:
    """Full trace of an orchestrated workflow execution."""

    trace_id: str
    session_id: str
    workflow: str
    steps: List[OrchestrationStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0
    success: bool = False


class AIOrchestrator:
    """AI Orchestrator — composes multi-step AI workflows.

    Responsibilities:
        - Coordinate Research → Agents → Features → Models flow
        - Compose Prediction → Signal → Strategy → Risk flow
        - Manage Intelligence Pipeline execution
        - Handle partial failures and fallbacks
        - Track orchestration traces

    Workflow types:
        - intelligence_pipeline: Full end-to-end (research to decision)
        - prediction_pipeline: Features to prediction
        - signal_pipeline: Prediction to signal
        - decision_pipeline: Signal to actionable decision
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self._adapters: Dict[str, Any] = {}
        self._traces: Dict[str, OrchestrationTrace] = {}
        self._started = False

    async def start(self) -> None:
        """Start the orchestrator."""
        logger.info("AI Orchestrator starting")
        self._started = True
        logger.info("AI Orchestrator ready")

    async def stop(self) -> None:
        """Stop the orchestrator."""
        logger.info("AI Orchestrator stopping")
        self._started = False
        self._traces.clear()
        logger.info("AI Orchestrator stopped")

    def _get_adapters(self) -> Dict[str, Any]:
        """Lazy-load adapters."""
        if not self._adapters:
            from .research_adapter import ResearchAdapter
            from .agent_adapter import AgentAdapter
            from .feature_adapter import FeatureAdapter
            from .ml_adapter import MLAdapter
            from .model_serving_adapter import ModelServingAdapter
            from .data_adapter import DataAdapter
            from .strategy_adapter import StrategyAdapter
            from .risk_adapter import RiskAdapter
            from .portfolio_adapter import PortfolioAdapter
            from .order_adapter import OrderAdapter
            from .execution_adapter import ExecutionAdapter

            self._adapters = {
                "research": ResearchAdapter(self.config),
                "agent": AgentAdapter(self.config),
                "feature": FeatureAdapter(self.config),
                "ml": MLAdapter(self.config),
                "model_serving": ModelServingAdapter(self.config),
                "data": DataAdapter(self.config),
                "strategy": StrategyAdapter(self.config),
                "risk": RiskAdapter(self.config),
                "portfolio": PortfolioAdapter(self.config),
                "order": OrderAdapter(self.config),
                "execution": ExecutionAdapter(self.config),
            }
        return self._adapters

    # ------------------------------------------------------------------
    # Core Workflow: Process
    # ------------------------------------------------------------------

    async def process(
        self,
        session: AISession,
        context: AIContext,
    ) -> AIContext:
        """Execute the full intelligence pipeline."""
        trace = OrchestrationTrace(
            trace_id=f"trace_{session.session_id}_{time.monotonic_ns()}",
            session_id=session.session_id,
            workflow="intelligence_pipeline",
        )

        try:
            adapters = self._get_adapters()

            # Step 1: Research
            if self.config.enable_research:
                context = await self._execute_step(
                    trace, "research",
                    adapters["research"].research(session),
                    context,
                )

            # Step 2: Agent Analysis
            if self.config.enable_agents:
                context = await self._execute_step(
                    trace, "agent_analysis",
                    adapters["agent"].analyze(session),
                    context,
                )

            # Step 3: Feature Extraction
            context = await self._execute_step(
                trace, "feature_extraction",
                adapters["feature"].get_features(session),
                context,
            )

            # Step 4: Model Prediction
            if self.config.enable_model_serving:
                context = await self._execute_step(
                    trace, "model_prediction",
                    self._predict(session, adapters),
                    context,
                )

            # Step 5: Signal Generation
            context = await self._execute_step(
                trace, "signal_generation",
                self._generate_signal_internal(session, adapters, context),
                context,
            )

            # Step 6: Strategy Validation
            if self.config.enable_strategy:
                context = await self._execute_step(
                    trace, "strategy_validation",
                    adapters["strategy"].validate(session),
                    context,
                )

            # Step 7: Risk Check
            if self.config.enable_risk:
                context = await self._execute_step(
                    trace, "risk_check",
                    adapters["risk"].check(session, context),
                    context,
                )

            # Step 8: Portfolio Check
            if self.config.enable_portfolio:
                context = await self._execute_step(
                    trace, "portfolio_check",
                    adapters["portfolio"].check(session),
                    context,
                )

            trace.success = True

        except Exception as exc:
            logger.error("Orchestration failed: %s", exc, exc_info=True)
            trace.success = False
            context.add_error(str(exc))

        finally:
            trace.completed_at = datetime.now(timezone.utc)
            trace.total_duration_ms = (
                (trace.completed_at - trace.started_at).total_seconds() * 1000
            )
            self._traces[trace.trace_id] = trace

        return context

    # ------------------------------------------------------------------
    # Simplified Workflows
    # ------------------------------------------------------------------

    async def research(self, session: AISession) -> AIContext:
        """Run AI research only."""
        adapters = self._get_adapters()
        context = AIContext(session=session)

        if self.config.enable_research:
            result = await adapters["research"].research(session)
            context.set_data("research", result)

        return context

    async def predict(self, session: AISession) -> AIContext:
        """Run prediction only."""
        adapters = self._get_adapters()
        context = AIContext(session=session)

        features = await adapters["feature"].get_features(session)
        prediction = await adapters["model_serving"].predict(session, features)
        context.set_data("prediction", prediction)
        context.set_data("features", features)

        return context

    async def generate_signal(self, session: AISession) -> AIContext:
        """Run signal generation only."""
        adapters = self._get_adapters()
        context = AIContext(session=session)

        features = await adapters["feature"].get_features(session)
        prediction = await adapters["model_serving"].predict(session, features)
        signal = await adapters["strategy"].generate_signal(session, prediction, features)
        context.set_data("signal", signal)
        context.has_signal = True

        return context

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    async def _predict(self, session: AISession, adapters: Dict[str, Any]):
        """Internal prediction flow."""
        features = await adapters["feature"].get_features(session)
        prediction = await adapters["model_serving"].predict(session, features)
        return {"features": features, "prediction": prediction}

    async def _generate_signal_internal(
        self,
        session: AISession,
        adapters: Dict[str, Any],
        context: AIContext,
    ):
        """Internal signal generation from context."""
        prediction = context.get_data("prediction") or context.get_data("model_prediction")
        features = context.get_data("features") or context.get_data("feature_extraction")

        if not prediction and self.config.enable_model_serving:
            features = await adapters["feature"].get_features(session)
            prediction = await adapters["model_serving"].predict(session, features)

        signal = await adapters["strategy"].generate_signal(session, prediction, features)
        context.has_signal = True
        return signal

    async def _execute_step(
        self,
        trace: OrchestrationTrace,
        step_name: str,
        coro,
        context: AIContext,
    ) -> AIContext:
        """Execute a single orchestration step with tracing."""
        step = OrchestrationStep(name=step_name, status="running")
        step.started_at = datetime.now(timezone.utc)
        trace.steps.append(step)

        try:
            result = await coro
            step.status = "completed"
            step.result = result
            context.set_data(step_name, result)

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.warning(
                "Orchestration step '%s' failed: %s",
                step_name, exc,
            )
            context.add_warning(f"{step_name}: {exc}")

        finally:
            step.completed_at = datetime.now(timezone.utc)
            step.duration_ms = (
                (step.completed_at - step.started_at).total_seconds() * 1000
            )

        return context

    # ------------------------------------------------------------------
    # Trace Management
    # ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Optional[OrchestrationTrace]:
        """Get an orchestration trace by ID."""
        return self._traces.get(trace_id)

    def get_session_traces(self, session_id: str) -> List[OrchestrationTrace]:
        """Get all traces for a session."""
        return [t for t in self._traces.values() if t.session_id == session_id]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Orchestrator health."""
        traces = list(self._traces.values())
        recent_traces = traces[-10:] if traces else []

        return {
            "started": self._started,
            "total_traces": len(traces),
            "successful_traces": sum(1 for t in traces if t.success),
            "failed_traces": sum(1 for t in traces if not t.success),
            "recent_traces": [
                {
                    "trace_id": t.trace_id[:20],
                    "workflow": t.workflow,
                    "success": t.success,
                    "duration_ms": round(t.total_duration_ms, 1),
                    "steps": len(t.steps),
                }
                for t in recent_traces
            ],
        }
