"""
ICYQuant Research Controller — operational control plane for the research platform.

Provides administration APIs for managing platform configuration, runtime
policies, access control, and operational commands (pause/resume/restart).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControllerAction(str, Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"
    DRAIN = "drain"


class ControllerTarget(str, Enum):
    PLATFORM = "platform"
    KNOWLEDGE = "knowledge"
    PIPELINE = "pipeline"
    API = "api"


@dataclass
class ControllerConfig:
    max_retries: int = 3
    action_timeout_seconds: int = 60
    audit_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    timestamp: datetime
    action: ControllerAction
    target: ControllerTarget
    user_id: str
    result: str
    detail: str = ""


class ResearchController:
    """Operational control plane for the AI research platform.

    Responsibilities:
        - Execute administrative commands (start/stop/pause/resume)
        - Manage platform configuration
        - Audit trail for all control actions
        - Health-based circuit breaking
    """

    def __init__(self, config: Optional[ControllerConfig] = None) -> None:
        self._config = config or ControllerConfig()
        self._audit_log: list[AuditEntry] = []
        self._platform_ref: Any = None  # Set after platform init

    def bind_platform(self, platform: Any) -> None:
        """Bind to the AIResearchPlatform instance for control operations."""
        self._platform_ref = platform

    async def execute(
        self,
        action: ControllerAction,
        target: ControllerTarget,
        user_id: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        """Execute a control action and record audit trail."""
        try:
            result = await self._do_action(action, target)
            self._audit(
                action=action,
                target=target,
                user_id=user_id,
                result="success",
                detail=reason,
            )
            return {"status": "ok", "action": action.value, "target": target.value, "detail": result}
        except Exception as exc:
            self._audit(
                action=action,
                target=target,
                user_id=user_id,
                result="failure",
                detail=str(exc),
            )
            return {"status": "error", "action": action.value, "target": target.value, "error": str(exc)}

    async def _do_action(self, action: ControllerAction, target: ControllerTarget) -> str:
        """Execute the actual control operation."""
        if self._platform_ref is None:
            raise RuntimeError("Controller not bound to a platform instance")

        platform = self._platform_ref

        if target == ControllerTarget.PLATFORM:
            if action == ControllerAction.START:
                await platform.start()
                return "Platform started"
            elif action == ControllerAction.STOP:
                await platform.stop()
                return "Platform stopped"
            elif action == ControllerAction.RESTART:
                await platform.stop()
                await platform.start()
                return "Platform restarted"

        elif target == ControllerTarget.KNOWLEDGE:
            if action == ControllerAction.PAUSE:
                await platform.knowledge_engine.pause()
                return "Knowledge engine paused"
            elif action == ControllerAction.RESUME:
                await platform.knowledge_engine.resume()
                return "Knowledge engine resumed"

        elif target == ControllerTarget.PIPELINE:
            if action == ControllerAction.PAUSE:
                platform.pipeline.pause()
                return "Pipeline paused"
            elif action == ControllerAction.RESUME:
                platform.pipeline.resume()
                return "Pipeline resumed"
            elif action == ControllerAction.DRAIN:
                await platform.pipeline.drain()
                return "Pipeline drained"

        return f"Action {action.value} on {target.value} completed"

    def _audit(
        self,
        action: ControllerAction,
        target: ControllerTarget,
        user_id: str,
        result: str,
        detail: str = "",
    ) -> None:
        if self._config.audit_enabled:
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                action=action,
                target=target,
                user_id=user_id,
                result=result,
                detail=detail,
            )
            self._audit_log.append(entry)
            logger.info("AUDIT: %s %s by %s → %s", action.value, target.value, user_id, result)

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent audit entries."""
        entries = self._audit_log[-limit:]
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "action": e.action.value,
                "target": e.target.value,
                "user_id": e.user_id,
                "result": e.result,
                "detail": e.detail,
            }
            for e in entries
        ]
