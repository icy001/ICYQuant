"""AI Runtime Adapter for the Service Mesh Platform.

Provides ``AIRuntimeAdapter`` for integrating AI Runtime with
the service mesh for model service, inference gateway, and
future AI Agent platform unified communication.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class AIRuntimeAdapter:
    """Adapter for integrating AI Runtime with the mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._model_handlers: Dict[str, Callable] = {}
        self._active_models: Dict[str, Dict[str, Any]] = {}
        self._inference_count = 0
        self._adapter_active = False

    async def initialize(self) -> Dict[str, Any]:
        self._adapter_active = True
        self._telemetry.log_platform_event(
            "ai_runtime_adapter_initialized", "ai_runtime",
        )
        logger.info("AI Runtime adapter initialized.")
        return {"success": True}

    async def shutdown(self) -> Dict[str, Any]:
        self._adapter_active = False
        self._telemetry.log_platform_event(
            "ai_runtime_adapter_shutdown", "ai_runtime",
        )
        logger.info("AI Runtime adapter shut down.")
        return {"success": True}

    @property
    def is_active(self) -> bool:
        return self._adapter_active

    def register_model_handler(
        self,
        model_name: str,
        handler: Callable,
    ) -> None:
        self._model_handlers[model_name] = handler

    async def deploy_model(
        self,
        model_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deploy a model through the mesh."""
        self._active_models[model_name] = {
            "model_name": model_name,
            "status": "deployed",
            "config": config or {},
            "deployed_at": datetime.utcnow().isoformat(),
        }

        self._telemetry.log_platform_event(
            "model_deployed", "ai_runtime",
            {"model_name": model_name},
        )
        logger.info("Model '%s' deployed.", model_name)
        return {"success": True, "model": model_name}

    async def undeploy_model(
        self, model_name: str
    ) -> Dict[str, Any]:
        """Undeploy a model."""
        self._active_models.pop(model_name, None)
        self._telemetry.log_platform_event(
            "model_undeployed", "ai_runtime",
            {"model_name": model_name},
        )
        return {"success": True, "model": model_name}

    async def inference(
        self,
        model_name: str,
        input_data: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run inference through the AI Runtime."""
        self._inference_count += 1

        handler = self._model_handlers.get(model_name)
        if handler is None:
            return {
                "success": False,
                "error": f"No handler for model: {model_name}",
            }

        self._metrics.increment_counter(
            "icyquant_mesh_ai_inference_total",
            labels={"model": model_name},
        )

        try:
            result = handler(input_data, config)
            if asyncio.iscoroutine(result):
                result = await result

            self._telemetry.log_platform_event(
                "inference_completed",
                "ai_runtime",
                {"model": model_name,
                 "inference_count": self._inference_count},
            )
            return {
                "success": True,
                "model": model_name,
                "result": result,
                "inference_id": f"inf-{int(time.monotonic())}",
            }
        except Exception as exc:
            self._telemetry.log_error(
                "ai_runtime_adapter",
                "inference_failed",
                str(exc),
                {"model": model_name},
            )
            return {
                "success": False,
                "error": str(exc),
                "model": model_name,
            }

    async def create_agent(
        self,
        agent_name: str,
        model_name: str,
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an AI Agent (reserved for future)."""
        agent_id = f"agent-{int(time.monotonic())}"
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "model": model_name,
            "tools": tools or [],
            "note": "AI Agent platform reserved for future",
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return list(self._active_models.values())

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": self._adapter_active,
                "inference_count": self._inference_count,
                "deployed_models": len(self._active_models),
                "handler_count": len(self._model_handlers),
                "models": list(self._active_models.keys()),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"AIRuntimeAdapter(active={self._adapter_active})"
            )
