"""Agent API - RESTful API for AI Trading Agent system.

Provides endpoints for:
- Agent status monitoring
- AI decision requests
- Decision explainability (why buy/sell/reject?)
- Workflow management
- System mode control
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.agents.service import AgentService, ServiceConfig
from services.agents.decision import FinalDecision

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standard API response wrapper."""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class AgentAPI:
    """Agent API - programmatic interface for the AI trading agent system.

    Usage:
        api = AgentAPI()
        api.start()

        # Query agent status
        status = api.get_agent_status()

        # Request AI decision
        result = api.request_decision("NVDA")

        # Get explainability
        reasons = api.get_decision_reasons(result["data"]["decision_id"])

        api.stop()
    """

    def __init__(self, config: ServiceConfig = None):
        self._service: Optional[AgentService] = None
        self._config = config or ServiceConfig()
        self._initialized = False

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> APIResponse:
        """Start the agent service."""
        try:
            self._service = AgentService(self._config)
            self._service.start()
            self._initialized = True
            return APIResponse(
                success=True,
                message="Agent service started",
                data={"status": self._service.status.value},
            )
        except Exception as e:
            logger.error("Failed to start agent service: %s", e)
            return APIResponse(
                success=False,
                error=str(e),
                message="Failed to start agent service",
            )

    def stop(self) -> APIResponse:
        """Stop the agent service."""
        try:
            if self._service:
                self._service.stop()
                self._initialized = False
            return APIResponse(success=True, message="Agent service stopped")
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def _ensure_service(self) -> Optional[APIResponse]:
        """Ensure service is initialized."""
        if not self._service or not self._initialized:
            return APIResponse(
                success=False,
                error="Service not initialized",
                message="Call start() first",
            )
        return None

    # ── Agent Status ────────────────────────────────────────────

    def get_agent_status(self) -> APIResponse:
        """GET /api/v1/agents/status - Get status of all agents."""
        error = self._ensure_service()
        if error:
            return error

        status = self._service.get_system_status()
        return APIResponse(
            success=True,
            data=status,
            message="Agent status retrieved",
        )

    def get_agent_health(self) -> APIResponse:
        """Get detailed agent health information."""
        error = self._ensure_service()
        if error:
            return error

        if not self._service.supervisor:
            return APIResponse(
                success=False,
                error="Supervisor not enabled",
                message="Cannot check health without supervisor",
            )

        health = self._service.supervisor.check_agent_health()
        return APIResponse(
            success=True,
            data=health,
            message="Agent health check completed",
        )

    # ── Decision Endpoints ──────────────────────────────────────

    def request_decision(self, symbol: str) -> APIResponse:
        """POST /api/v1/agents/decision - Request AI trading decision.

        Args:
            symbol: Trading symbol (e.g., "NVDA", "AAPL")

        Returns:
            Decision with action, confidence, risk assessment
        """
        error = self._ensure_service()
        if error:
            return error

        try:
            result = self._service.request_decision(symbol)
            return APIResponse(
                success=True,
                data=result,
                message=f"Decision for {symbol}: {result.get('decision', 'unknown')}",
            )
        except Exception as e:
            logger.error("Decision request failed: %s", e)
            return APIResponse(
                success=False,
                error=str(e),
                message=f"Failed to make decision for {symbol}",
            )

    def batch_request_decisions(self, symbols: List[str]) -> APIResponse:
        """Request decisions for multiple symbols."""
        error = self._ensure_service()
        if error:
            return error

        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self._service.request_decision(symbol)
            except Exception as e:
                results[symbol] = {"error": str(e)}

        return APIResponse(
            success=True,
            data=results,
            message=f"Decisions for {len(symbols)} symbols",
        )

    # ── Decision Explainability ─────────────────────────────────

    def get_decision_reasons(self, decision_id: str) -> APIResponse:
        """GET /api/v1/agents/logs - Get reasons behind a decision.

        Explains:
        - Why was the decision made?
        - What were the scores?
        - What warnings were raised?
        """
        error = self._ensure_service()
        if error:
            return error

        reasons = self._service.get_decision_reasons(decision_id)
        if not reasons:
            return APIResponse(
                success=False,
                error="Decision not found",
                message=f"No decision with ID {decision_id}",
            )

        return APIResponse(
            success=True,
            data=reasons,
            message="Decision reasons retrieved",
        )

    def get_agent_logs(
        self, agent_type: str = None, limit: int = 50
    ) -> APIResponse:
        """GET /api/v1/agents/logs - Get agent decision logs."""
        error = self._ensure_service()
        if error:
            return error

        logs = self._service.get_agent_logs(agent_type=agent_type, limit=limit)
        return APIResponse(
            success=True,
            data=logs,
            message=f"Retrieved logs ({logs.get('total_entries', 0)} entries)",
        )

    def get_decision_history(self, limit: int = 50) -> APIResponse:
        """Get historical decisions."""
        error = self._ensure_service()
        if error:
            return error

        decisions = self._service.decision_engine.get_decisions(limit=limit)
        return APIResponse(
            success=True,
            data=decisions,
            message=f"Retrieved {len(decisions)} historical decisions",
        )

    # ── Workflow Endpoints ──────────────────────────────────────

    def start_workflow(
        self, name: str, context: Dict[str, Any] = None
    ) -> APIResponse:
        """Start a trading workflow."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.start_workflow(name, context)
        if "error" in result:
            return APIResponse(
                success=False,
                error=result["error"],
                message="Workflow not found",
            )

        return APIResponse(
            success=True,
            data=result,
            message=f"Workflow '{name}' started",
        )

    def get_workflow_status(self, run_id: str) -> APIResponse:
        """Get workflow run status."""
        error = self._ensure_service()
        if error:
            return error

        status = self._service.get_workflow_status(run_id)
        if not status:
            return APIResponse(
                success=False,
                error="Run not found",
                message=f"No workflow run with ID {run_id}",
            )

        return APIResponse(
            success=True,
            data=status,
            message="Workflow status retrieved",
        )

    def cancel_workflow(self, run_id: str) -> APIResponse:
        """Cancel a running workflow."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.cancel_workflow(run_id)
        return APIResponse(
            success=result.get("cancelled", False),
            data=result,
            message="Workflow cancelled" if result.get("cancelled") else "Cancellation failed",
        )

    def list_workflows(self) -> APIResponse:
        """List available workflows."""
        error = self._ensure_service()
        if error:
            return error

        workflows = self._service.workflow_engine.get_available_workflows()
        definitions = {
            w: self._service.workflow_engine.get_workflow_definition(w)
            for w in workflows
        }

        return APIResponse(
            success=True,
            data={"workflows": workflows, "definitions": definitions},
            message=f"{len(workflows)} workflows available",
        )

    # ── Portfolio & Risk ────────────────────────────────────────

    def request_portfolio_review(
        self, portfolio_id: str = "default"
    ) -> APIResponse:
        """Request a portfolio review."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.request_portfolio_review(portfolio_id)
        return APIResponse(
            success=True,
            data=result,
            message="Portfolio review completed",
        )

    def request_risk_check(
        self, metrics: Dict[str, Any] = None
    ) -> APIResponse:
        """Request a risk check."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.request_risk_check(metrics)
        return APIResponse(
            success=True,
            data=result,
            message="Risk check completed",
        )

    def get_risk_rejections(self, limit: int = 50) -> APIResponse:
        """Get recent risk rejection reasons."""
        error = self._ensure_service()
        if error:
            return error

        if not self._service.risk_agent:
            return APIResponse(
                success=False,
                error="Risk agent not enabled",
            )

        rejections = self._service.risk_agent.get_rejection_reasons(limit=limit)
        return APIResponse(
            success=True,
            data=rejections,
            message=f"Retrieved {len(rejections)} rejection reasons",
        )

    # ── System Management ───────────────────────────────────────

    def set_system_mode(self, mode: str) -> APIResponse:
        """Set system operating mode."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.set_system_mode(mode)
        if "error" in result:
            return APIResponse(
                success=False,
                error=result["error"],
                message="Invalid mode",
            )

        return APIResponse(
            success=True,
            data=result,
            message=f"Mode set to {result['mode']}",
        )

    def update_decision_weights(
        self, weights: Dict[str, float]
    ) -> APIResponse:
        """Update decision engine component weights."""
        error = self._ensure_service()
        if error:
            return error

        result = self._service.update_decision_weights(weights)
        return APIResponse(
            success=True,
            data=result,
            message="Decision weights updated",
        )

    def get_system_summary(self) -> APIResponse:
        """Get full system summary."""
        error = self._ensure_service()
        if error:
            return error

        summary = self._service.get_summary()
        return APIResponse(
            success=True,
            data=summary,
            message="System summary retrieved",
        )

    # ── Policy Management ───────────────────────────────────────

    def get_policies(self) -> APIResponse:
        """Get all active policies."""
        error = self._ensure_service()
        if error:
            return error

        status = self._service.policy_engine.get_status()
        return APIResponse(
            success=True,
            data=status,
            message="Policies retrieved",
        )
