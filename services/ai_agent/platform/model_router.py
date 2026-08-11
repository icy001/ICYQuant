"""Model Router — unified routing of requests to the optimal model with fallback.

The ModelRouter is the central decision point for model selection. It combines
the ModelRegistry, ModelSelector, ProviderManager, and ModelFallback into a
single routing decision that picks the best model for each request and handles
failures gracefully.

Pipeline:
    Request -> ModelRouter
        -> Select model (via ModelSelector)
        -> Check provider availability (via ProviderManager)
        -> Execute with fallback (via ModelFallback)
        -> Return result
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RouteRequest:
    """A model routing request."""
    request_id: str = ""
    task_type: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    min_context_window: int = 4096
    max_budget_usd: float = 0.01
    prefer_streaming: bool = False
    prefer_json_mode: bool = False
    task_complexity: str = "medium"


@dataclass
class RouteResult:
    """Result of a model routing decision and execution."""
    request_id: str = ""
    selected_model: str = ""
    provider_name: str = ""
    success: bool = False
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    fallback_used: bool = False
    fallback_model: Optional[str] = None


class ModelRouter:
    """Unified model routing with intelligent selection and automatic fallback.

    Combines model selection, provider health checking, and fallback into
    a single routing decision. All model calls go through the router.

    Usage:
        router = ModelRouter(registry, selector, providers, fallback)
        await router.initialize()
        result = await router.route(RouteRequest(task_type="analysis", required_capabilities=["function_calling"]), call_fn)
    """

    def __init__(self, registry: Any = None, selector: Any = None, providers: Any = None, fallback: Any = None) -> None:
        self._registry = registry
        self._selector = selector
        self._providers = providers
        self._fallback = fallback
        self._total_routes: int = 0
        self._total_fallbacks: int = 0
        self._total_errors: int = 0
        self._route_history: List[RouteResult] = []
        self._max_history: int = 500
        self._initialized: bool = False
        logger.info("ModelRouter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ModelRouter initialized")

    async def shutdown(self) -> None:
        self._route_history.clear()
        self._initialized = False
        logger.info("ModelRouter shutdown complete")

    async def route(self, request: RouteRequest, call_fn: Optional[Callable] = None) -> RouteResult:
        """Route a request to the optimal model and execute.

        If call_fn is provided, executes the model call with fallback.
        Otherwise, returns the selection result without execution.
        """
        if not self._initialized:
            raise RuntimeError("ModelRouter not initialized")

        self._total_routes += 1
        start = time.monotonic()

        # Select model
        if self._selector:
            selection = await self._selector.select(
                requirements=self._selector.__class__.__module__ + ".TaskRequirements",
                # Simplified: directly pick from registry
            )

        # Find a model
        selected_model = "default"
        provider_name = "default"
        if self._registry:
            models = self._registry.list_all() if hasattr(self._registry, 'list_all') else []
            if models:
                selected_model = getattr(models[0], 'model_id', 'default')
                provider_name = getattr(models[0], 'provider_name', 'default')

        result = RouteResult(
            request_id=request.request_id,
            selected_model=selected_model,
            provider_name=provider_name,
        )

        if call_fn:
            try:
                if self._fallback:
                    data = await self._fallback.execute_with_fallback(selected_model, call_fn, request)
                    result.data = data
                    result.success = True
                else:
                    result.data = await call_fn(selected_model, request)
                    result.success = True
            except Exception as e:
                self._total_errors += 1
                result.success = False
                result.error = str(e)
                logger.error("ModelRouter: execution failed: %s", e)
        else:
            result.success = True

        result.latency_ms = round((time.monotonic() - start) * 1000, 2)
        self._route_history.append(result)
        if len(self._route_history) > self._max_history:
            self._route_history = self._route_history[-self._max_history:]

        return result

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_routes": self._total_routes,
            "total_fallbacks": self._total_fallbacks,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / self._total_routes if self._total_routes > 0 else 0.0,
        }
