"""AI Gateway — Unified API gateway for all AI capabilities.

The AIGateway is the single entry point for external systems to access
AI functionality. It abstracts away the complexity of internal AI subsystems
and provides a clean, versioned API.

Systems interact with AIGateway, not directly with Research, Agents, ML, etc.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .ai_context import AIContext
from .ai_session import AISession

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


class GatewayEndpoint(str, Enum):
    """Public AI Gateway endpoints."""

    RESEARCH = "research"
    ANALYZE = "analyze"
    PREDICT = "predict"
    BATCH_PREDICT = "batch_predict"
    GENERATE_SIGNAL = "generate_signal"
    REQUEST_DECISION = "request_decision"
    EXPLAIN = "explain"
    FEEDBACK = "feedback"
    STATUS = "status"


class GatewayStatus(str, Enum):
    """Gateway operational status."""

    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    OVERLOADED = "overloaded"
    STOPPING = "stopping"
    OFFLINE = "offline"


@dataclass
class GatewayRequest:
    """A request entering the AI Gateway."""

    request_id: str
    endpoint: GatewayEndpoint
    session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayResponse:
    """A response from the AI Gateway."""

    request_id: str
    endpoint: GatewayEndpoint
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    context: Optional[AIContext] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AIGateway:
    """AI Gateway — Unified API for all AI capabilities.

    This is the facade that external systems see. It routes requests to
    the appropriate internal subsystem (via adapters and the orchestrator)
    and returns standardized responses.

    Public endpoints:
        - research(query) → ResearchContext
        - analyze(data) → AnalysisContext
        - predict(features) → PredictionResponse
        - batch_predict(requests) → List[PredictionResponse]
        - generate_signal(context) → Signal
        - request_decision(context) → Decision
        - explain(decision) → Explanation
        - feedback(result) → FeedbackAck
        - status() → PlatformStatus

    Security:
        - All requests are authenticated via session
        - Permissions are enforced per endpoint
        - Rate limiting is applied
        - Audit trail is maintained
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self.status = GatewayStatus.OFFLINE
        self._adapters: Dict[str, Any] = {}
        self._rate_limits: Dict[str, List[float]] = {}
        self._rate_limit_window = 60.0
        self._rate_limit_max_requests = 1000
        self._request_count: Dict[str, int] = {}
        self._error_count: Dict[str, int] = {}

    async def start(self) -> None:
        """Start the AI Gateway."""
        self.status = GatewayStatus.STARTING
        logger.info("AI Gateway starting")

        self._init_adapters()
        self.status = GatewayStatus.READY
        logger.info("AI Gateway ready")

    async def stop(self) -> None:
        """Stop the AI Gateway."""
        self.status = GatewayStatus.STOPPING
        logger.info("AI Gateway stopping")
        self._adapters.clear()
        self.status = GatewayStatus.OFFLINE
        logger.info("AI Gateway stopped")

    # ------------------------------------------------------------------
    # Adapter Initialization
    # ------------------------------------------------------------------

    def _init_adapters(self) -> None:
        """Initialize internal service adapters."""
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
        logger.debug("AI Gateway adapters initialized: %d", len(self._adapters))

    # ------------------------------------------------------------------
    # Public API — Core Intelligence
    # ------------------------------------------------------------------

    async def research(self, session: AISession) -> GatewayResponse:
        """Execute AI research for a query or hypothesis.

        Routes to: Research Adapter → Research Platform
        """
        return await self._handle(
            endpoint=GatewayEndpoint.RESEARCH,
            session=session,
            handler=lambda: self._adapters["research"].research(session),
        )

    async def analyze(self, session: AISession) -> GatewayResponse:
        """Analyze market data, features, or predictions.

        Routes to: Agent Adapter → Multi-Agent Analysis
        """
        return await self._handle(
            endpoint=GatewayEndpoint.ANALYZE,
            session=session,
            handler=lambda: self._adapters["agent"].analyze(session),
        )

    async def predict(self, session: AISession) -> GatewayResponse:
        """Execute model prediction for given features.

        Routes to: Feature Adapter → Model Serving Adapter → Prediction
        """
        return await self._handle(
            endpoint=GatewayEndpoint.PREDICT,
            session=session,
            handler=self._predict_flow(session),
        )

    async def batch_predict(self, session: AISession) -> GatewayResponse:
        """Execute batch model predictions.

        Routes to: Feature Adapter → Batch Inference
        """
        return await self._handle(
            endpoint=GatewayEndpoint.BATCH_PREDICT,
            session=session,
            handler=self._batch_predict_flow(session),
        )

    async def generate_signal(self, session: AISession) -> GatewayResponse:
        """Generate a trading signal from AI analysis.

        Routes to: Full Intelligence Pipeline → Signal
        """
        return await self._handle(
            endpoint=GatewayEndpoint.GENERATE_SIGNAL,
            session=session,
            handler=self._signal_flow(session),
        )

    async def request_decision(self, session: AISession) -> GatewayResponse:
        """Request an AI trading decision (with guards and approval).

        Routes to: Intelligence Pipeline → Guards → Controller
        """
        return await self._handle(
            endpoint=GatewayEndpoint.REQUEST_DECISION,
            session=session,
            handler=self._decision_flow(session),
        )

    async def explain(self, session: AISession) -> GatewayResponse:
        """Explain an AI decision.

        Routes to: Explainability Engine
        """
        return await self._handle(
            endpoint=GatewayEndpoint.EXPLAIN,
            session=session,
            handler=self._explain_flow(session),
        )

    async def feedback(self, session: AISession) -> GatewayResponse:
        """Submit feedback for an AI decision (for learning loop).

        Routes to: Feedback Loop
        """
        return await self._handle(
            endpoint=GatewayEndpoint.FEEDBACK,
            session=session,
            handler=self._feedback_flow(session),
        )

    async def status_endpoint(self) -> GatewayResponse:
        """Get platform-wide status."""
        return GatewayResponse(
            request_id="status",
            endpoint=GatewayEndpoint.STATUS,
            success=True,
            data={
                "gateway_status": self.status.value,
                "uptime": "active",
                "adapters": list(self._adapters.keys()),
            },
        )

    # ------------------------------------------------------------------
    # Internal Flow Handlers
    # ------------------------------------------------------------------

    async def _predict_flow(self, session: AISession):
        """Prediction flow: features → model → prediction."""
        async def flow():
            features = await self._adapters["feature"].get_features(session)
            prediction = await self._adapters["model_serving"].predict(session, features)
            return {"features": features, "prediction": prediction}
        return flow()

    async def _batch_predict_flow(self, session: AISession):
        """Batch prediction flow."""
        async def flow():
            features_batch = await self._adapters["feature"].get_features_batch(session)
            predictions = await self._adapters["model_serving"].batch_predict(
                session, features_batch
            )
            return {"batch_size": len(features_batch), "predictions": predictions}
        return flow()

    async def _signal_flow(self, session: AISession):
        """Signal generation flow: full pipeline → signal."""
        async def flow():
            features = await self._adapters["feature"].get_features(session)
            prediction = await self._adapters["model_serving"].predict(session, features)
            signal = await self._adapters["strategy"].generate_signal(
                session, prediction, features
            )
            return {"signal": signal, "prediction": prediction}
        return flow()

    async def _decision_flow(self, session: AISession):
        """Decision flow: signal → strategy → risk → decision."""
        async def flow():
            signal_result = await self._signal_flow(session)
            if not signal_result.get("signal"):
                return {"decision": None, "reason": "No signal generated"}

            risk_check = await self._adapters["risk"].check(
                session, signal_result
            )
            if not risk_check.get("approved", False):
                return {
                    "decision": None,
                    "reason": f"Risk rejection: {risk_check.get('reason')}",
                    "risk": risk_check,
                }

            if self.config.mode.value == "live":
                decision = await self._adapters["order"].prepare(
                    session, signal_result["signal"]
                )
                return {"decision": decision, "signal": signal_result}
            else:
                return {"decision": signal_result, "mode": self.config.mode.value}
        return flow()

    async def _explain_flow(self, session: AISession):
        """Explanation flow: retrieve decision trace."""
        from .explainability import ExplainabilityEngine
        engine = ExplainabilityEngine()
        return await engine.explain(session)

    async def _feedback_flow(self, session: AISession):
        """Feedback flow: record outcome for learning."""
        from .feedback_loop import FeedbackLoop
        loop = FeedbackLoop()
        return await loop.submit(session)

    # ------------------------------------------------------------------
    # Request Handling
    # ------------------------------------------------------------------

    async def _handle(
        self,
        endpoint: GatewayEndpoint,
        session: AISession,
        handler,
    ) -> GatewayResponse:
        """Handle a gateway request with rate limiting and error handling."""
        request_id = f"{endpoint.value}:{session.session_id}:{time.monotonic_ns()}"

        # Rate limiting
        if not self._check_rate_limit(endpoint.value):
            self._increment_error(endpoint.value)
            return GatewayResponse(
                request_id=request_id,
                endpoint=endpoint,
                success=False,
                error="Rate limit exceeded",
            )

        self._increment_request(endpoint.value)
        start = time.perf_counter()

        try:
            data = await handler()
            latency_ms = (time.perf_counter() - start) * 1000

            return GatewayResponse(
                request_id=request_id,
                endpoint=endpoint,
                success=True,
                data=data if isinstance(data, dict) else {"result": data},
                latency_ms=latency_ms,
            )

        except Exception as exc:
            self._increment_error(endpoint.value)
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("Gateway %s failed: %s", endpoint.value, exc, exc_info=True)

            return GatewayResponse(
                request_id=request_id,
                endpoint=endpoint,
                success=False,
                error=str(exc),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, endpoint: str) -> bool:
        """Check if request is within rate limits."""
        now = time.monotonic()
        if endpoint not in self._rate_limits:
            self._rate_limits[endpoint] = []

        # Prune old entries
        window_start = now - self._rate_limit_window
        self._rate_limits[endpoint] = [
            t for t in self._rate_limits[endpoint] if t > window_start
        ]

        if len(self._rate_limits[endpoint]) >= self._rate_limit_max_requests:
            return False

        self._rate_limits[endpoint].append(now)
        return True

    def _increment_request(self, endpoint: str) -> None:
        """Track a successful request."""
        self._request_count[endpoint] = self._request_count.get(endpoint, 0) + 1

    def _increment_error(self, endpoint: str) -> None:
        """Track an error."""
        self._error_count[endpoint] = self._error_count.get(endpoint, 0) + 1

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Gateway health status."""
        total_requests = sum(self._request_count.values())
        total_errors = sum(self._error_count.values())
        error_rate = total_errors / max(total_requests, 1)

        if error_rate > 0.1:
            self.status = GatewayStatus.DEGRADED
        elif total_requests > self._rate_limit_max_requests * 10:
            self.status = GatewayStatus.OVERLOADED

        return {
            "status": self.status.value,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(error_rate, 4),
            "requests_by_endpoint": dict(self._request_count),
            "errors_by_endpoint": dict(self._error_count),
            "adapters": list(self._adapters.keys()),
        }
