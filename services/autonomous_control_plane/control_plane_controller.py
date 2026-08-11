"""
Control Plane Controller — Request/dispatch interface for the Control Plane.

Provides a clean API boundary that external systems use to interact
with the governance layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControllerAction(Enum):
    """Actions the controller can dispatch to the control plane."""
    EVALUATE_DECISION = "evaluate_decision"
    PROMOTE_MODEL = "promote_model"
    DEMOTE_MODEL = "demote_model"
    ROLLBACK_MODEL = "rollback_model"
    QUARANTINE_MODEL = "quarantine_model"
    HUMAN_OVERRIDE = "human_override"
    KILL_SWITCH = "kill_switch"
    GET_HEALTH = "get_health"
    GET_DECISION_LINEAGE = "get_decision_lineage"
    GET_POLICY = "get_policy"
    UPDATE_POLICY = "update_policy"
    GET_AUTONOMY_LEVEL = "get_autonomy_level"
    SET_AUTONOMY_LEVEL = "set_autonomy_level"
    GET_BUDGET = "get_budget"
    REPORT_INCIDENT = "report_incident"


@dataclass
class ControllerRequest:
    """Standardized request format for control plane operations."""
    action: ControllerAction
    payload: dict = None
    trace_id: str = ""
    operator: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}


@dataclass
class ControllerResponse:
    """Standardized response format from control plane operations."""
    action: ControllerAction
    success: bool
    data: Any = None
    error: Optional[str] = None
    trace_id: str = ""
    decision_id: Optional[str] = None


class ControlPlaneController:
    """
    Controller for dispatching requests to the Control Plane.

    This is the primary API boundary — all external interactions with
    the governance layer go through this controller.
    """

    def __init__(self, control_plane=None):
        self._control_plane = control_plane
        self._request_count = 0
        self._error_count = 0

    def bind(self, control_plane) -> None:
        """Bind to a ControlPlane instance."""
        self._control_plane = control_plane

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: ControllerRequest) -> ControllerResponse:
        """Route a request to the appropriate handler."""
        self._request_count += 1

        if not self._control_plane:
            self._error_count += 1
            return ControllerResponse(
                action=request.action,
                success=False,
                error="ControlPlane not bound",
                trace_id=request.trace_id,
            )

        handlers = {
            ControllerAction.EVALUATE_DECISION: self._handle_evaluate,
            ControllerAction.PROMOTE_MODEL: self._handle_promote,
            ControllerAction.DEMOTE_MODEL: self._handle_demote,
            ControllerAction.ROLLBACK_MODEL: self._handle_rollback,
            ControllerAction.QUARANTINE_MODEL: self._handle_quarantine,
            ControllerAction.HUMAN_OVERRIDE: self._handle_human_override,
            ControllerAction.KILL_SWITCH: self._handle_kill_switch,
            ControllerAction.GET_HEALTH: self._handle_get_health,
            ControllerAction.GET_DECISION_LINEAGE: self._handle_get_lineage,
            ControllerAction.GET_AUTONOMY_LEVEL: self._handle_get_autonomy,
            ControllerAction.REPORT_INCIDENT: self._handle_report_incident,
        }

        handler = handlers.get(request.action)
        if not handler:
            self._error_count += 1
            return ControllerResponse(
                action=request.action,
                success=False,
                error=f"Unknown action: {request.action.value}",
                trace_id=request.trace_id,
            )

        try:
            return await handler(request)
        except Exception as e:
            self._error_count += 1
            logger.exception("Controller dispatch error: %s", e)
            return ControllerResponse(
                action=request.action,
                success=False,
                error=str(e),
                trace_id=request.trace_id,
            )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_evaluate(self, req: ControllerRequest) -> ControllerResponse:
        from .control_plane import ControlPlaneContext
        context = ControlPlaneContext(**req.payload.get("context", {}))
        result = await self._control_plane.evaluate(context)
        return ControllerResponse(
            action=req.action,
            success=True,
            data={"decision": result.value},
            trace_id=context.trace_id,
            decision_id=context.trace_id,
        )

    async def _handle_promote(self, req: ControllerRequest) -> ControllerResponse:
        model_id = req.payload["model_id"]
        target = req.payload["target_state"]
        ok = await self._control_plane.promote_model(model_id, target)
        return ControllerResponse(action=req.action, success=ok, trace_id=req.trace_id)

    async def _handle_demote(self, req: ControllerRequest) -> ControllerResponse:
        ok = await self._control_plane.demote_model(
            req.payload["model_id"], req.payload.get("reason", "")
        )
        return ControllerResponse(action=req.action, success=ok, trace_id=req.trace_id)

    async def _handle_rollback(self, req: ControllerRequest) -> ControllerResponse:
        ok = await self._control_plane.rollback_model(
            req.payload["model_id"], req.payload["target_version"]
        )
        return ControllerResponse(action=req.action, success=ok, trace_id=req.trace_id)

    async def _handle_quarantine(self, req: ControllerRequest) -> ControllerResponse:
        ok = await self._control_plane.quarantine_model(
            req.payload["model_id"], req.payload.get("reason", "")
        )
        return ControllerResponse(action=req.action, success=ok, trace_id=req.trace_id)

    async def _handle_human_override(self, req: ControllerRequest) -> ControllerResponse:
        ok = await self._control_plane.human_override(
            req.payload["decision_id"],
            req.payload["action"],
            req.operator,
            req.payload.get("reason", ""),
        )
        return ControllerResponse(action=req.action, success=ok, trace_id=req.trace_id)

    async def _handle_kill_switch(self, req: ControllerRequest) -> ControllerResponse:
        await self._control_plane.trigger_kill_switch(req.payload.get("reason", "manual"))
        return ControllerResponse(action=req.action, success=True, trace_id=req.trace_id)

    async def _handle_get_health(self, req: ControllerRequest) -> ControllerResponse:
        stats = self._control_plane.stats()
        return ControllerResponse(action=req.action, success=True, data=stats)

    async def _handle_get_lineage(self, req: ControllerRequest) -> ControllerResponse:
        lineage = await self._control_plane.decision_engine.get_lineage(
            req.payload.get("decision_id")
        ) if self._control_plane.decision_engine else {}
        return ControllerResponse(action=req.action, success=True, data=lineage)

    async def _handle_get_autonomy(self, req: ControllerRequest) -> ControllerResponse:
        level = await self._control_plane.autonomy_engine.current_level() if self._control_plane.autonomy_engine else 0
        return ControllerResponse(action=req.action, success=True, data={"level": level})

    async def _handle_report_incident(self, req: ControllerRequest) -> ControllerResponse:
        if self._control_plane.incident_manager:
            await self._control_plane.incident_manager.create_incident(
                req.payload.get("incident_type", "unknown"),
                req.payload.get("description", ""),
                req.payload.get("severity", "warning"),
            )
        return ControllerResponse(action=req.action, success=True, trace_id=req.trace_id)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "requests_total": self._request_count,
            "errors_total": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
        }
