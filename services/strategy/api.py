"""
Strategy Management API — REST endpoints for the Production Strategy Platform.

Exposes endpoints for strategy deployment, lifecycle management,
snapshot operations, recovery, and health inspection.

Endpoints:
    POST   /strategy/deploy      — Deploy a strategy
    POST   /strategy/start       — Start a strategy
    POST   /strategy/stop        — Stop a strategy
    POST   /strategy/pause       — Pause a strategy
    POST   /strategy/resume      — Resume a strategy
    POST   /strategy/restart     — Restart a strategy
    POST   /strategy/rollback    — Rollback to version
    POST   /strategy/snapshot    — Take a snapshot
    POST   /strategy/recover     — Recover from snapshot
    GET    /strategy/status      — Get strategy status
    GET    /strategy/list        — List strategies
    GET    /strategy/versions    — List versions
    GET    /strategy/snapshots   — List snapshots
    GET    /strategy/history     — Get recovery history
    GET    /strategy/health      — Platform health
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIError:
    """Standardized API error response."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class APIResponse:
    """Standardized API response."""
    success: bool
    data: Any = None
    error: Optional[APIError] = None
    request_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def ok(cls, data: Any, request_id: str = "") -> "APIResponse":
        return cls(success=True, data=data, request_id=request_id)

    @classmethod
    def fail(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None,
             request_id: str = "") -> "APIResponse":
        return cls(success=False, error=APIError(code=code, message=message, details=details),
                   request_id=request_id)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.success:
            d["data"] = self.data
        else:
            d["error"] = self.error.to_dict() if self.error else {"code": "unknown", "message": "Unknown error"}
        return d


class StrategyAPI:
    """REST API for the Production Strategy Platform.

    Accepts a StrategyEngine instance and exposes all management
    endpoints for strategy lifecycle, snapshot, and recovery operations.

    Usage:
        engine = StrategyEngine()
        await engine.initialize()

        api = StrategyAPI(engine)

        # Deploy
        resp = await api.deploy(request_body)
        # Start
        resp = await api.start(request_body)
    """

    def __init__(self, engine: Any) -> None:
        """
        Args:
            engine: An initialized StrategyEngine instance.
        """
        self.engine = engine
        self._routes: Dict[str, Callable] = {}
        logger.info("StrategyAPI initializing")
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all API route handlers."""
        self._routes = {
            "POST /strategy/deploy": self._handle_deploy,
            "POST /strategy/start": self._handle_start,
            "POST /strategy/stop": self._handle_stop,
            "POST /strategy/pause": self._handle_pause,
            "POST /strategy/resume": self._handle_resume,
            "POST /strategy/restart": self._handle_restart,
            "POST /strategy/rollback": self._handle_rollback,
            "POST /strategy/snapshot": self._handle_snapshot,
            "POST /strategy/recover": self._handle_recover,
            "GET  /strategy/status": self._handle_status,
            "GET  /strategy/list": self._handle_list,
            "GET  /strategy/versions": self._handle_versions,
            "GET  /strategy/snapshots": self._handle_snapshots,
            "GET  /strategy/history": self._handle_history,
            "GET  /strategy/health": self._handle_health,
            "GET  /strategy/metrics": self._handle_metrics,
        }

    # ── Handlers ──

    async def dispatch(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Dispatch an API request to the appropriate handler."""
        import uuid

        request_id = uuid.uuid4().hex[:12]
        key = f"{method.upper()} {path}"

        if key not in self._routes:
            return APIResponse.fail("NOT_FOUND", f"Unknown route: {method} {path}", request_id=request_id)

        try:
            handler = self._routes[key]
            result = await handler(body or {}, request_id)
            return result
        except Exception as e:
            logger.exception("API error: %s %s", method, path)
            return APIResponse.fail("INTERNAL_ERROR", str(e), request_id=request_id)

    # ── Deploy ──

    async def _handle_deploy(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        from .strategy_engine import DeployRequest
        from .strategy_loader import PackageSource

        source_data = body.get("source", {})
        request = DeployRequest(
            source=PackageSource(**source_data),
            config=body.get("config", {}),
            strategy_id=body.get("strategy_id", ""),
            deploy_mode=body.get("deploy_mode", "production"),
            force=body.get("force", False),
            metadata=body.get("metadata", {}),
        )
        result = await self.engine.deploy(request)
        return APIResponse.ok({
            "strategy_id": result.strategy_id,
            "version": result.version,
            "state": result.state.value if hasattr(result.state, "value") else str(result.state),
            "validation": result.validation.to_dict() if result.validation else None,
            "deploy_time_ms": result.deploy_time_ms,
        }, request_id)

    # ── Lifecycle ──

    async def _handle_start(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.start(strategy_id)
        return _op_response(result, request_id)

    async def _handle_stop(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.stop(strategy_id)
        return _op_response(result, request_id)

    async def _handle_pause(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.pause(strategy_id)
        return _op_response(result, request_id)

    async def _handle_resume(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.resume(strategy_id)
        return _op_response(result, request_id)

    async def _handle_restart(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.restart(strategy_id)
        return _op_response(result, request_id)

    async def _handle_rollback(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        version = _require(body, "target_version")
        result = await self.engine.rollback(strategy_id, version)
        return APIResponse.ok({
            "strategy_id": result.strategy_id,
            "version": result.version,
            "state": result.state.value if hasattr(result.state, "value") else str(result.state),
            "success": result.success,
            "error": result.error,
        }, request_id)

    # ── Snapshot & Recovery ──

    async def _handle_snapshot(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.snapshot(strategy_id)
        return _op_response(result, request_id)

    async def _handle_recover(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        snapshot_id = body.get("snapshot_id")
        result = await self.engine.recover(strategy_id, snapshot_id)
        return _op_response(result, request_id)

    # ── Query ──

    async def _handle_status(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.status(strategy_id)
        return APIResponse.ok(result, request_id)

    async def _handle_list(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        state = body.get("state")
        active_only = body.get("active_only", False)
        result = await self.engine.list_strategies(state=state, active_only=active_only)
        return APIResponse.ok({"strategies": result, "count": len(result)}, request_id)

    async def _handle_versions(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        result = await self.engine.list_versions(strategy_id)
        return APIResponse.ok(result, request_id)

    async def _handle_snapshots(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = _require(body, "strategy_id")
        limit = body.get("limit", 20)
        snapshots = self.engine.snapshot_manager.list_snapshots(strategy_id, limit=limit)
        return APIResponse.ok({"strategy_id": strategy_id, "snapshots": snapshots}, request_id)

    async def _handle_history(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        strategy_id = body.get("strategy_id")
        limit = body.get("limit", 50)
        history = self.engine.recovery.get_history(strategy_id=strategy_id, limit=limit)
        return APIResponse.ok({"history": history, "count": len(history)}, request_id)

    async def _handle_health(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        summary = self.engine.get_summary()
        return APIResponse.ok(summary, request_id)

    async def _handle_metrics(self, body: Dict[str, Any], request_id: str) -> APIResponse:
        runtime_summary = self.engine.runtime.get_summary()
        registry_summary = self.engine.registry.get_summary()
        snapshot_summary = self.engine.snapshot_manager.get_summary()
        recovery_summary = self.engine.recovery.get_summary()
        return APIResponse.ok({
            "runtime": runtime_summary,
            "registry": registry_summary,
            "snapshots": snapshot_summary,
            "recovery": recovery_summary,
        }, request_id)

    # ── Utilities ──

    def list_routes(self) -> List[str]:
        """Return all registered API routes."""
        return list(self._routes.keys())


def _require(body: Dict[str, Any], key: str) -> Any:
    """Extract required field or raise ValueError."""
    if key not in body:
        raise ValueError(f"Missing required field: {key}")
    return body[key]


def _op_response(result: Any, request_id: str) -> APIResponse:
    """Standardize OperationResult to APIResponse."""
    return APIResponse.ok({
        "success": result.success,
        "strategy_id": result.strategy_id,
        "action": result.action,
        "previous_state": result.previous_state.value if hasattr(result.previous_state, "value") else str(result.previous_state) if result.previous_state else None,
        "new_state": result.new_state.value if hasattr(result.new_state, "value") else str(result.new_state) if result.new_state else None,
        "message": result.message,
        "duration_ms": result.duration_ms,
    }, request_id)
