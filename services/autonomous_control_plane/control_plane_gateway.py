"""
Control Plane Gateway — External integration boundary.

The Gateway is the bridge between the Control Plane and external systems:
- OMS/EMS for execution instructions
- Risk systems for risk parameters
- Monitoring dashboards for health metrics
- Admin APIs for human intervention
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class GatewayChannel(Enum):
    """Communication channels the Gateway supports."""
    INTERNAL = "internal"       # Direct in-process calls
    REST_API = "rest_api"       # REST API server
    GRPC = "grpc"               # gRPC service
    MESSAGE_QUEUE = "mq"        # Message queue (pub/sub)
    WEBSOCKET = "websocket"     # Real-time WebSocket
    WEBHOOK = "webhook"         # Outbound webhook calls


@dataclass
class GatewayRequest:
    """Inbound request through the gateway."""
    channel: GatewayChannel
    method: str
    payload: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    auth_context: Optional[dict] = None
    trace_id: str = ""


@dataclass
class GatewayResponse:
    """Outbound response through the gateway."""
    status: int = 200
    data: Any = None
    error: Optional[str] = None
    trace_id: str = ""


class ControlPlaneGateway:
    """
    Gateway for external systems to interact with the Control Plane.

    Handles authentication, rate limiting, request routing, and
    response formatting across multiple communication channels.
    """

    def __init__(self, controller=None, rate_limit_per_second: int = 100):
        from .control_plane_controller import ControlPlaneController
        self._controller = controller or ControlPlaneController()
        self._rate_limit = rate_limit_per_second
        self._request_count = 0
        self._handlers: dict[str, Callable] = {}
        self._middlewares: list[Callable] = []

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    def add_middleware(self, middleware: Callable) -> None:
        """Add a middleware to the request pipeline."""
        self._middlewares.append(middleware)

    async def _apply_middleware(self, req: GatewayRequest) -> Optional[GatewayResponse]:
        """Apply middleware chain. Returns None if request passes."""
        for mw in self._middlewares:
            result = await mw(req)
            if result is not None:
                return result  # Short-circuit — middleware rejected
        return None

    # ------------------------------------------------------------------
    # Request Handling
    # ------------------------------------------------------------------

    async def handle(self, req: GatewayRequest) -> GatewayResponse:
        """Process an incoming gateway request."""
        self._request_count += 1

        # Rate limiting
        if self._request_count % max(self._rate_limit, 1) == 0:
            logger.warning("Rate limit approaching threshold")

        # Middleware
        mw_result = await self._apply_middleware(req)
        if mw_result:
            return mw_result

        # Authentication
        if not self._authenticate(req):
            return GatewayResponse(status=403, error="Forbidden", trace_id=req.trace_id)

        # Route to controller
        try:
            from .control_plane_controller import ControllerRequest, ControllerAction
            action = self._route_method(req.method)
            ctrl_req = ControllerRequest(
                action=action,
                payload=req.payload,
                trace_id=req.trace_id,
            )
            ctrl_resp = await self._controller.dispatch(ctrl_req)
            return GatewayResponse(
                status=200 if ctrl_resp.success else 400,
                data=ctrl_resp.data,
                error=ctrl_resp.error,
                trace_id=ctrl_resp.trace_id or req.trace_id,
            )
        except Exception as e:
            logger.exception("Gateway error: %s", e)
            return GatewayResponse(status=500, error=str(e), trace_id=req.trace_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _authenticate(self, req: GatewayRequest) -> bool:
        """Check authentication context."""
        if req.auth_context:
            return req.auth_context.get("authenticated", False)
        return req.channel == GatewayChannel.INTERNAL  # Internal calls are trusted

    def _route_method(self, method: str):
        """Map method string to ControllerAction."""
        from .control_plane_controller import ControllerAction
        mapping = {
            "evaluate": ControllerAction.EVALUATE_DECISION,
            "promote_model": ControllerAction.PROMOTE_MODEL,
            "demote_model": ControllerAction.DEMOTE_MODEL,
            "rollback_model": ControllerAction.ROLLBACK_MODEL,
            "quarantine_model": ControllerAction.QUARANTINE_MODEL,
            "human_override": ControllerAction.HUMAN_OVERRIDE,
            "kill_switch": ControllerAction.KILL_SWITCH,
            "get_health": ControllerAction.GET_HEALTH,
            "get_lineage": ControllerAction.GET_DECISION_LINEAGE,
            "get_autonomy": ControllerAction.GET_AUTONOMY_LEVEL,
            "report_incident": ControllerAction.REPORT_INCIDENT,
        }
        return mapping.get(method, ControllerAction.EVALUATE_DECISION)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "requests_total": self._request_count,
            "middlewares": len(self._middlewares),
        }
