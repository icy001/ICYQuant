"""Inference Infrastructure Layer.

Backend components for model serving:
- gRPC server: high-performance inference RPC service
- REST server: HTTP-based inference API
- worker_pool: concurrent inference worker management
- batch_scheduler: dynamic batching for throughput optimization
"""

from __future__ import annotations

from infrastructure.inference.grpc_server import GRPCServer, GRPCServerConfig, InferenceServiceServicer
from infrastructure.inference.rest_server import RESTServer, RESTServerConfig
from infrastructure.inference.worker_pool import WorkerPool, WorkerConfig, InferenceWorker, WorkerStatus
from infrastructure.inference.batch_scheduler import BatchScheduler, BatchConfig, BatchRequest, BatchResult

__all__ = [
    "GRPCServer",
    "GRPCServerConfig",
    "InferenceServiceServicer",
    "RESTServer",
    "RESTServerConfig",
    "WorkerPool",
    "WorkerConfig",
    "InferenceWorker",
    "WorkerStatus",
    "BatchScheduler",
    "BatchConfig",
    "BatchRequest",
    "BatchResult",
]
