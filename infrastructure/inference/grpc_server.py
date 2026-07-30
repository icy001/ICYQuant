"""gRPC Inference Server — high-performance model serving endpoint.

Provides a low-latency gRPC interface for model inference, suitable
for production trading systems requiring microsecond-level prediction
with strongly-typed contracts.

Note: This is a design-validated stub; full gRPC integration requires
the `grpcio` package and proto compilation.

Usage::

    server = GRPCServer(config=GRPCServerConfig(port=50051))
    server.register_service(predict_fn)
    server.start()
    server.wait_for_termination()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


@dataclass
class GRPCServerConfig:
    """gRPC server configuration.

    Attributes:
        host: Bind address.
        port: Bind port.
        max_workers: Thread pool size.
        max_message_length_mb: Max gRPC message size.
        enable_reflection: Enable gRPC server reflection.
        enable_health_check: Enable gRPC health checking.
        tls_cert_path: TLS certificate path (optional).
        tls_key_path: TLS key path (optional).
    """

    host: str = "0.0.0.0"
    port: int = 50051
    max_workers: int = 10
    max_message_length_mb: int = 100
    enable_reflection: bool = True
    enable_health_check: bool = True
    tls_cert_path: str = ""
    tls_key_path: str = ""


class InferenceServiceServicer:
    """gRPC servicer for inference service.

    Implements the Predict and PredictBatch RPCs. In production,
    this would be generated from a .proto definition.

    Methods:
        Predict(symbol, features) → prediction, confidence
        PredictBatch(symbols, features_list) → predictions, confidences
        GetModelStatus() → model info
        HealthCheck() → serving → healthy
    """

    def __init__(self, serving_service: Any = None):
        self._service = serving_service
        self._request_count: int = 0

    def Predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single prediction RPC."""
        self._request_count += 1
        if not self._service:
            return {"prediction": 0.0, "confidence": 0.0, "error": "no service"}

        try:
            result = self._service.predict(
                symbol=request.get("symbol", ""),
                features=request.get("features"),
                model_name=request.get("model_name"),
                market=request.get("market", "US"),
            )
            return {
                "symbol": result.symbol,
                "prediction": result.prediction,
                "confidence": result.confidence,
                "signal": result.signal.value if hasattr(result.signal, 'value') else str(result.signal),
                "model_name": result.model_name,
                "latency_ms": result.latency_ms,
            }
        except Exception as e:
            return {"prediction": 0.0, "confidence": 0.0, "error": str(e)}

    def PredictBatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch prediction RPC."""
        if not self._service:
            return {"results": [], "error": "no service"}

        try:
            results = self._service.predict_batch(
                symbols=request.get("symbols", []),
                features_list=request.get("features_list"),
                market=request.get("market", "US"),
            )
            return {
                "results": [
                    {
                        "symbol": r.symbol,
                        "prediction": r.prediction,
                        "confidence": r.confidence,
                        "signal": r.signal.value if hasattr(r.signal, 'value') else str(r.signal),
                    }
                    for r in results
                ],
            }
        except Exception as e:
            return {"results": [], "error": str(e)}

    def GetModelStatus(self) -> Dict[str, Any]:
        """Get model serving status."""
        if self._service:
            return self._service.get_status()
        return {"status": "no service"}

    def HealthCheck(self) -> Dict[str, Any]:
        """gRPC health check."""
        if self._service:
            health = self._service.health()
            return {"status": health.value if hasattr(health, 'value') else str(health)}
        return {"status": "SERVING"}


class GRPCServer:
    """High-performance gRPC inference server.

    In production, this wraps the grpcio server with TLS, authentication,
    and reflection. The current implementation provides a thread-based
    mock for development and testing.

    Usage::

        server = GRPCServer(config=GRPCServerConfig(port=50051))
        server.register_service(serving_service)
        server.start()
        server.wait_for_termination()
    """

    def __init__(self, config: Optional[GRPCServerConfig] = None):
        self.config = config or GRPCServerConfig()
        self._servicer: Optional[InferenceServiceServicer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._predict_count: int = 0

    def register_service(self, serving_service: Any) -> None:
        """Register the serving service with the gRPC servicer."""
        self._servicer = InferenceServiceServicer(serving_service)

    def start(self) -> None:
        """Start the gRPC server."""
        if self._running:
            return

        # In production: grpc.server(futures.ThreadPoolExecutor(...))
        # server.add_insecure_port(f'{host}:{port}')
        # server.start()
        self._running = True

    def stop(self) -> None:
        """Stop the gRPC server gracefully."""
        self._running = False

    def wait_for_termination(self) -> None:
        """Block until server stops."""
        while self._running:
            time.sleep(0.1)

    def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Direct predict call (bypassing gRPC, for testing)."""
        if not self._servicer:
            return {"error": "no servicer registered"}
        return self._servicer.Predict(request)

    def predict_batch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Direct batch predict call."""
        if not self._servicer:
            return {"error": "no servicer registered"}
        return self._servicer.PredictBatch(request)

    @property
    def is_running(self) -> bool:
        return self._running
