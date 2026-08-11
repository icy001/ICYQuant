"""AI Control Plane — Unified management and governance layer.

The AI Control Plane is the administrative backbone of the AI Platform.
It manages agent lifecycle, model deployment, policy enforcement,
permissions, and monitoring across all AI subsystems.

Architecture:
    AI Control Plane
        ├── Agent Control (lifecycle, scaling)
        ├── Model Control (deployment, versioning, rollback)
        └── Policy Control (permissions, guardrails, approval)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


class ControlAction(str, Enum):
    """Actions managed by the control plane."""

    DEPLOY_MODEL = "deploy_model"
    ROLLBACK_MODEL = "rollback_model"
    PROMOTE_MODEL = "promote_model"
    ARCHIVE_MODEL = "archive_model"
    START_AGENT = "start_agent"
    STOP_AGENT = "stop_agent"
    RESTART_AGENT = "restart_agent"
    UPDATE_POLICY = "update_policy"
    REVOKE_PERMISSION = "revoke_permission"
    GRANT_PERMISSION = "grant_permission"
    FORCE_APPROVAL = "force_approval"
    EMERGENCY_STOP = "emergency_stop"


class ControlPlaneMode(str, Enum):
    """Control plane operating modes."""

    NORMAL = "normal"
    READ_ONLY = "read_only"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


@dataclass
class ControlEvent:
    """An action recorded by the control plane."""

    event_id: str
    action: ControlAction
    target: str
    operator: str = "system"
    status: str = "completed"
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AgentController:
    """Manages agent lifecycle (start, stop, scale)."""

    def __init__(self) -> None:
        self._agents: Dict[str, Dict[str, Any]] = {}

    async def start_agent(self, agent_name: str) -> Dict[str, Any]:
        self._agents[agent_name] = {"status": "running", "name": agent_name}
        logger.info("Agent started: %s", agent_name)
        return self._agents[agent_name]

    async def stop_agent(self, agent_name: str) -> Dict[str, Any]:
        if agent_name in self._agents:
            self._agents[agent_name]["status"] = "stopped"
        logger.info("Agent stopped: %s", agent_name)
        return self._agents.get(agent_name, {})

    async def list_agents(self) -> List[Dict[str, Any]]:
        return list(self._agents.values())

    async def health(self) -> Dict[str, Any]:
        return {
            "total_agents": len(self._agents),
            "running": sum(1 for a in self._agents.values() if a.get("status") == "running"),
            "agents": {
                name: info.get("status", "unknown")
                for name, info in self._agents.items()
            },
        }


class ModelController:
    """Manages model deployment, versioning, and rollback."""

    def __init__(self) -> None:
        self._deployments: Dict[str, Dict[str, Any]] = {}
        self._rollback_history: List[Dict[str, Any]] = []

    async def deploy_model(self, model_id: str, version: str) -> Dict[str, Any]:
        key = f"{model_id}:{version}"
        self._deployments[key] = {
            "model_id": model_id,
            "version": version,
            "status": "deployed",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Model deployed: %s v%s", model_id, version)
        return self._deployments[key]

    async def rollback_model(self, model_id: str, to_version: str) -> Dict[str, Any]:
        self._rollback_history.append({
            "model_id": model_id,
            "to_version": to_version,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        })
        key = f"{model_id}:{to_version}"
        self._deployments[key] = {
            "model_id": model_id,
            "version": to_version,
            "status": "rolled_back",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Model rolled back: %s → v%s", model_id, to_version)
        return self._deployments[key]

    async def list_deployments(self) -> List[Dict[str, Any]]:
        return list(self._deployments.values())

    async def health(self) -> Dict[str, Any]:
        return {
            "deployments": len(self._deployments),
            "rollbacks": len(self._rollback_history),
            "models": {
                k: v["status"] for k, v in self._deployments.items()
            },
        }


class PolicyController:
    """Manages AI policies, permissions, guardrails, and approval rules."""

    def __init__(self) -> None:
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._default_policies()

    def _default_policies(self) -> None:
        self._policies = {
            "max_position_size": {
                "value": 0.10,
                "description": "Maximum position size as fraction of portfolio",
            },
            "min_confidence_threshold": {
                "value": 0.60,
                "description": "Minimum confidence for auto-approval",
            },
            "require_approval_above": {
                "value": 0.05,
                "description": "Require approval for positions above this fraction",
            },
            "max_daily_signals": {
                "value": 50,
                "description": "Maximum AI-generated signals per day",
            },
            "enable_learning_loop": {
                "value": True,
                "description": "Whether to enable automated learning",
            },
        }

    async def get_policy(self, name: str) -> Optional[Dict[str, Any]]:
        return self._policies.get(name)

    async def set_policy(self, name: str, value: Any, description: str = "") -> Dict[str, Any]:
        self._policies[name] = {"value": value, "description": description}
        logger.info("Policy updated: %s = %s", name, value)
        return self._policies[name]

    async def list_policies(self) -> Dict[str, Any]:
        return dict(self._policies)

    async def evaluate(self, context: Dict[str, Any]) -> Dict[str, bool]:
        results = {}
        for name, policy in self._policies.items():
            actual = context.get(name)
            if actual is not None:
                results[name] = actual <= policy["value"] if isinstance(actual, (int, float)) else True
        return results


class AIControlPlane:
    """AI Control Plane — administrative backbone of the AI Platform.

    Provides centralized control over:
        - Agent lifecycle management
        - Model deployment and rollback
        - Policy enforcement
        - Permissions management
        - Emergency controls

    This is the layer that ensures AI operates within defined boundaries
    and can be administratively controlled at any time.
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self.mode = ControlPlaneMode.NORMAL
        self.agent_controller = AgentController()
        self.model_controller = ModelController()
        self.policy_controller = PolicyController()
        self._events: List[ControlEvent] = []
        self._started = False

    async def start(self) -> None:
        """Start the control plane."""
        self._started = True
        logger.info(
            "AI Control Plane starting (mode=%s, config_mode=%s)",
            self.mode.value,
            self.config.mode.value,
        )
        logger.info("AI Control Plane ready")

    async def stop(self) -> None:
        """Stop the control plane."""
        logger.info("AI Control Plane stopping")
        self._started = False
        logger.info("AI Control Plane stopped")

    # ------------------------------------------------------------------
    # Agent Control
    # ------------------------------------------------------------------

    async def start_agent(self, agent_name: str) -> Dict[str, Any]:
        """Start an AI agent."""
        result = await self.agent_controller.start_agent(agent_name)
        await self._record_event(ControlAction.START_AGENT, agent_name, result)
        return result

    async def stop_agent(self, agent_name: str) -> Dict[str, Any]:
        """Stop an AI agent."""
        result = await self.agent_controller.stop_agent(agent_name)
        await self._record_event(ControlAction.STOP_AGENT, agent_name, result)
        return result

    # ------------------------------------------------------------------
    # Model Control
    # ------------------------------------------------------------------

    async def deploy_model(self, model_id: str, version: str) -> Dict[str, Any]:
        """Deploy a model version."""
        result = await self.model_controller.deploy_model(model_id, version)
        await self._record_event(ControlAction.DEPLOY_MODEL, f"{model_id}:{version}", result)
        return result

    async def rollback_model(self, model_id: str, to_version: str) -> Dict[str, Any]:
        """Roll back a model deployment."""
        result = await self.model_controller.rollback_model(model_id, to_version)
        await self._record_event(
            ControlAction.ROLLBACK_MODEL, f"{model_id}:{to_version}", result
        )
        return result

    # ------------------------------------------------------------------
    # Policy Control
    # ------------------------------------------------------------------

    async def update_policy(self, name: str, value: Any) -> Dict[str, Any]:
        """Update an AI policy."""
        result = await self.policy_controller.set_policy(name, value)
        await self._record_event(ControlAction.UPDATE_POLICY, name, result)
        return result

    async def get_policies(self) -> Dict[str, Any]:
        """Get all policies."""
        return await self.policy_controller.list_policies()

    # ------------------------------------------------------------------
    # Emergency Controls
    # ------------------------------------------------------------------

    async def emergency_stop(self, reason: str = "") -> Dict[str, Any]:
        """Emergency stop — halt all AI-initiated actions immediately."""
        self.mode = ControlPlaneMode.EMERGENCY

        # Stop all agents
        agents = await self.agent_controller.list_agents()
        for agent in agents:
            await self.agent_controller.stop_agent(agent.get("name", ""))

        await self._record_event(
            ControlAction.EMERGENCY_STOP, "platform", {"reason": reason}
        )

        logger.critical("EMERGENCY STOP: %s", reason)
        return {"status": "emergency_stopped", "reason": reason}

    # ------------------------------------------------------------------
    # Event Recording
    # ------------------------------------------------------------------

    async def _record_event(
        self,
        action: ControlAction,
        target: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a control plane event."""
        event = ControlEvent(
            event_id=f"ctrl_{action.value}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            action=action,
            target=target,
            details=details,
        )
        self._events.append(event)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Control plane health."""
        return {
            "started": self._started,
            "mode": self.mode.value,
            "agent_control": await self.agent_controller.health(),
            "model_control": await self.model_controller.health(),
            "total_events": len(self._events),
            "recent_events": [
                {
                    "action": e.action.value,
                    "target": e.target,
                    "status": e.status,
                    "created_at": e.created_at.isoformat(),
                }
                for e in self._events[-5:]
            ],
        }
