"""Blue-Green deployment for ICYQuant Service Mesh.

Provides ``BlueGreenDeployer`` for zero-downtime blue-green
deployments with automatic validation and fast rollback.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BlueGreenPhase:
    """Blue-green deployment phases."""

    BLUE = "blue"
    GREEN_DEPLOY = "green_deploy"
    VALIDATION = "validation"
    TRAFFIC_SWITCH = "traffic_switch"
    BLUE_OFFLINE = "blue_offline"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class BlueGreenDeployer:
    """Manages blue-green deployment."""

    def __init__(
        self,
        validation_fn: Optional[Callable] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._validation_fn = validation_fn or (
            lambda: True
        )
        self._deployments: Dict[str, Dict[str, Any]] = {}
        self._active_deployment: Optional[str] = None
        self._event_count = 0

    def start_deployment(
        self,
        deployment_id: str,
        blue_version: str,
        green_version: str,
        blue_host: str,
        green_host: str,
    ) -> Dict[str, Any]:
        """Start a blue-green deployment."""
        with self._lock:
            self._event_count += 1
            deployment = {
                "deployment_id": deployment_id,
                "blue_version": blue_version,
                "green_version": green_version,
                "blue_host": blue_host,
                "green_host": green_host,
                "phase": BlueGreenPhase.BLUE,
                "created_at": datetime.utcnow().isoformat(),
                "history": [
                    {
                        "phase": BlueGreenPhase.BLUE,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ],
            }
            self._deployments[deployment_id] = deployment
            self._active_deployment = deployment_id
            return self._get_deployment_status(deployment_id)

    async def advance_phase(
        self, deployment_id: str
    ) -> Dict[str, Any]:
        """Advance to the next deployment phase."""
        with self._lock:
            deployment = self._deployments.get(deployment_id)
            if not deployment:
                return {"success": False, "error": "not_found"}

            phase = deployment["phase"]
            next_phase = self._get_next_phase(phase)

            if next_phase == BlueGreenPhase.VALIDATION:
                passed = self._validation_fn()
                if not passed:
                    deployment["phase"] = BlueGreenPhase.ROLLED_BACK
                    deployment["history"].append({
                        "phase": BlueGreenPhase.ROLLED_BACK,
                        "reason": "validation_failed",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    return self._get_deployment_status(deployment_id)

            deployment["phase"] = next_phase
            deployment["history"].append({
                "phase": next_phase,
                "timestamp": datetime.utcnow().isoformat(),
            })
            self._event_count += 1
            return self._get_deployment_status(deployment_id)

    async def rollback(
        self, deployment_id: str, reason: str = ""
    ) -> Dict[str, Any]:
        """Rollback a deployment."""
        with self._lock:
            deployment = self._deployments.get(deployment_id)
            if not deployment:
                return {"success": False, "error": "not_found"}
            deployment["phase"] = BlueGreenPhase.ROLLED_BACK
            deployment["history"].append({
                "phase": BlueGreenPhase.ROLLED_BACK,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            })
            self._event_count += 1
            return self._get_deployment_status(deployment_id)

    def _get_next_phase(
        self, current_phase: str
    ) -> str:
        phase_map = {
            BlueGreenPhase.BLUE: BlueGreenPhase.GREEN_DEPLOY,
            BlueGreenPhase.GREEN_DEPLOY: BlueGreenPhase.VALIDATION,
            BlueGreenPhase.VALIDATION: BlueGreenPhase.TRAFFIC_SWITCH,
            BlueGreenPhase.TRAFFIC_SWITCH: BlueGreenPhase.BLUE_OFFLINE,
            BlueGreenPhase.BLUE_OFFLINE: BlueGreenPhase.COMPLETED,
        }
        return phase_map.get(current_phase, current_phase)

    def _get_deployment_status(
        self, deployment_id: str
    ) -> Dict[str, Any]:
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return {"success": False}
        return {
            "deployment_id": deployment["deployment_id"],
            "phase": deployment["phase"],
            "blue_host": deployment["blue_host"],
            "green_host": deployment["green_host"],
            "history": deployment["history"],
            "active": deployment_id == self._active_deployment,
        }

    def get_deployment(
        self, deployment_id: str
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._get_deployment_status(deployment_id)

    def list_deployments(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                self._get_deployment_status(d_id)
                for d_id in self._deployments
            ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "deployment_count": len(self._deployments),
                "active_deployment": self._active_deployment,
                "event_count": self._event_count,
            }