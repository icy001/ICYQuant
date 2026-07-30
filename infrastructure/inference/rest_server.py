"""REST Inference Server — HTTP-based prediction API.

Provides a FastAPI-compatible REST interface for model inference
with JSON request/response, Swagger docs, and health endpoints.

Usage::

    server = RESTServer(config=RESTServerConfig(port=8100))
    server.register_service(serving_service)
    server.start()
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RESTServerConfig:
    """REST server configuration.

    Attributes:
        host: Bind address.
        port: Bind port.
        workers: Number of uvicorn workers.
        enable_docs: Enable Swagger/ReDoc.
        enable_cors: Enable CORS for all origins.
        request_timeout_ms: Request timeout.
        max_request_size_mb: Max request body size.
    """

    host: str = "0.0.0.0"
    port: int = 8100
    workers: int = 4
    enable_docs: bool = True
    enable_cors: bool = True
    request_timeout_ms: int = 5000
    max_request_size_mb: int = 50


class RESTServer:
    """REST API server for model inference.

    Provides endpoints:
        POST /api/v1/inference/predict     - Single prediction
        POST /api/v1/inference/predict/batch - Batch prediction
        GET  /api/v1/inference/model        - Model status
        POST /api/v1/inference/deploy       - Deploy model
        GET  /api/v1/inference/health       - Health check
        GET  /api/v1/inference/stats        - Monitoring stats

    Usage::

        server = RESTServer(config=RESTServerConfig(port=8100))
        server.register_service(serving_service)
        server.start()
    """

    def __init__(self, config: Optional[RESTServerConfig] = None):
        self.config = config or RESTServerConfig()
        self._service: Any = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._routes: Dict[str, Callable] = {}
        self._start_time: float = 0.0

    def register_service(self, serving_service: Any) -> None:
        """Register the serving service for request handling."""
        self._service = serving_service

    def start(self) -> None:
        """Start the REST server."""
        if self._running:
            return
        self._start_time = time.time()
        self._running = True

    def stop(self) -> None:
        """Stop the REST server."""
        self._running = False

    # ---- Request handlers (callable directly for testing) ----

    def handle_predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST /api/v1/inference/predict"""
        if not self._service:
            return {"error": "Serving service not registered"}

        symbol = data.get("symbol", "")
        features = data.get("features")
        model_name = data.get("model_name")
        market = data.get("market", "US")

        if not symbol:
            return {"error": "symbol is required", "status": 400}

        result = self._service.predict(
            symbol=symbol,
            features=features,
            model_name=model_name,
            market=market,
        )

        return {
            "symbol": result.symbol,
            "prediction": result.prediction,
            "confidence": result.confidence,
            "signal": result.signal.value if hasattr(result.signal, 'value') else str(result.signal),
            "model_name": result.model_name,
            "latency_ms": result.latency_ms,
            "cached": result.cached,
        }

    def handle_predict_batch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST /api/v1/inference/predict/batch"""
        if not self._service:
            return {"error": "Serving service not registered"}

        symbols = data.get("symbols", [])
        features_list = data.get("features_list")
        market = data.get("market", "US")

        results = self._service.predict_batch(
            symbols=symbols,
            features_list=features_list,
            market=market,
        )

        return {
            "results": [
                {
                    "symbol": r.symbol,
                    "prediction": r.prediction,
                    "confidence": r.confidence,
                    "signal": r.signal.value if hasattr(r.signal, 'value') else str(r.signal),
                    "model_name": r.model_name,
                    "latency_ms": r.latency_ms,
                }
                for r in results
            ],
        }

    def handle_get_model(self) -> Dict[str, Any]:
        """Handle GET /api/v1/inference/model"""
        if not self._service:
            return {"error": "Serving service not registered"}

        status = self._service.get_status()
        active = status.get("active_versions", {})
        models = status.get("models", [])

        return {
            "models": models,
            "active_versions": active,
            "mode": status.get("mode", "unknown"),
            "total_loaded": len(models),
        }

    def handle_deploy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST /api/v1/inference/deploy"""
        if not self._service:
            return {"error": "Serving service not registered"}

        model_name = data.get("model", "")
        strategy = data.get("strategy", "immediate")
        version = data.get("version", "")

        if not model_name:
            return {"error": "model is required"}

        result = self._service.deploy(model_name, version, strategy=strategy)
        return {
            "model": result.model_name,
            "version": result.version,
            "strategy": result.strategy.value if hasattr(result.strategy, 'value') else str(result.strategy),
            "success": result.success,
            "message": result.message,
        }

    def handle_health(self) -> Dict[str, Any]:
        """Handle GET /api/v1/inference/health"""
        if self._service:
            health = self._service.health()
            return {
                "status": health.value if hasattr(health, 'value') else str(health),
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }
        return {"status": "not_started"}

    def handle_stats(self) -> Dict[str, Any]:
        """Handle GET /api/v1/inference/stats"""
        if self._service:
            return self._service.get_monitor_stats()
        return {"error": "Serving service not registered"}

    @property
    def is_running(self) -> bool:
        return self._running
