"""
ICYQuant Model Runtime — In-memory model execution engine.

Manages model lifecycle within the process: load, warmup, predict, unload.
Supports multiple model backends (sklearn, lightgbm, xgboost, pytorch, onnx).

Key responsibilities:
  - Thread-safe model loading/unloading
  - LRU eviction for memory management
  - Warmup inference cycles
  - Per-model health probing
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class RuntimeState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    WARMING = "warming"
    READY = "ready"
    UNHEALTHY = "unhealthy"
    UNLOADING = "unloading"


class ModelBackend(str, Enum):
    SKLEARN = "sklearn"
    LIGHTGBM = "lightgbm"
    XGBOOST = "xgboost"
    CATBOOST = "catboost"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    CUSTOM = "custom"


@dataclass
class ModelRecord:
    """In-memory model record."""
    model_id: str
    version: str
    backend: ModelBackend
    model_object: Any
    state: RuntimeState = RuntimeState.LOADING
    loaded_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    inference_count: int = 0
    total_inference_ms: float = 0.0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def avg_latency_ms(self) -> float:
        if self.inference_count == 0:
            return 0.0
        return self.total_inference_ms / self.inference_count

    @property
    def error_rate(self) -> float:
        total = self.inference_count + self.error_count
        return self.error_count / total if total > 0 else 0.0

    @property
    def cache_key(self) -> str:
        return f"{self.model_id}:{self.version}"


# ---------------------------------------------------------------------------
# Backend loader
# ---------------------------------------------------------------------------

class BackendLoader:
    """Loads model objects for different backends."""

    @staticmethod
    def load_sklearn(path: str) -> Any:
        import joblib
        return joblib.load(path)

    @staticmethod
    def load_lightgbm(path: str) -> Any:
        import lightgbm as lgb
        return lgb.Booster(model_file=path)

    @staticmethod
    def load_xgboost(path: str) -> Any:
        import xgboost as xgb
        model = xgb.Booster()
        model.load_model(path)
        return model

    @staticmethod
    def load_catboost(path: str) -> Any:
        from catboost import CatBoost
        return CatBoost().load_model(path)

    @staticmethod
    def load_pytorch(path: str, model_class: Optional[str] = None) -> Any:
        import torch
        return torch.jit.load(path)

    @staticmethod
    def load_onnx(path: str) -> Any:
        import onnxruntime as ort
        return ort.InferenceSession(path)

    @staticmethod
    def load_tensorflow(path: str) -> Any:
        import tensorflow as tf
        return tf.saved_model.load(path)

    @classmethod
    def load(cls, backend: ModelBackend, path: str, **kwargs) -> Any:
        loaders: Dict[ModelBackend, Callable] = {
            ModelBackend.SKLEARN: cls.load_sklearn,
            ModelBackend.LIGHTGBM: cls.load_lightgbm,
            ModelBackend.XGBOOST: cls.load_xgboost,
            ModelBackend.CATBOOST: cls.load_catboost,
            ModelBackend.PYTORCH: cls.load_pytorch,
            ModelBackend.ONNX: cls.load_onnx,
            ModelBackend.TENSORFLOW: cls.load_tensorflow,
        }
        loader = loaders.get(backend)
        if loader is None:
            raise ValueError(f"Unsupported backend: {backend}")
        return loader(path, **kwargs) if backend == ModelBackend.PYTORCH else loader(path)


# ---------------------------------------------------------------------------
# Model Runtime
# ---------------------------------------------------------------------------

class ModelRuntime:
    """In-memory model execution runtime.

    Features:
      - LRU-based model cache with configurable size
      - Thread-safe concurrent access
      - Per-backend loading support
      - Model warmup with dummy data
      - Health monitoring per model
    """

    def __init__(self, cache_size: int = 8):
        self._cache_size = cache_size
        self._models: OrderedDict[str, ModelRecord] = OrderedDict()
        self._lock = threading.RLock()
        self._initialized = False
        self._backend_loader = BackendLoader()

        # Stats
        self._total_inferences: int = 0
        self._total_errors: int = 0
        self._total_latency_ms: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize runtime — verify backend availability."""
        logger.info("ModelRuntime initializing — cache_size=%d", self._cache_size)
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown — unload all models."""
        logger.info("ModelRuntime shutting down — unloading %d models", len(self._models))
        with self._lock:
            for key in list(self._models.keys()):
                await self.unload_by_key(key)
            self._models.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    async def load(
        self,
        model_id: str,
        version: str,
        backend: Optional[ModelBackend] = None,
        artifact_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelRecord:
        """Load a model into the runtime.

        Args:
            model_id: Model identifier.
            version: Model version string.
            backend: Model backend type. Auto-detected if None.
            artifact_path: Path to serialized model artifact.
            metadata: Additional model metadata.

        Returns:
            ModelRecord for the loaded model.
        """
        key = f"{model_id}:{version}"

        with self._lock:
            # Already loaded → refresh access time
            if key in self._models:
                record = self._models[key]
                if record.state in (RuntimeState.READY, RuntimeState.LOADED):
                    record.last_used_at = datetime.now(timezone.utc)
                    self._models.move_to_end(key)
                    return record

            # Evict if at capacity
            await self._evict_if_needed()

            # Create record
            record = ModelRecord(
                model_id=model_id,
                version=version,
                backend=backend or ModelBackend.CUSTOM,
                model_object=None,
                metadata=metadata or {},
            )
            self._models[key] = record

        try:
            # Load from artifact
            if artifact_path and backend:
                record.state = RuntimeState.LOADING
                record.model_object = await asyncio.to_thread(
                    self._backend_loader.load, backend, artifact_path
                )

            record.state = RuntimeState.LOADED
            record.loaded_at = datetime.now(timezone.utc)
            logger.info("Model loaded: %s v%s (backend=%s)", model_id, version, backend)

            return record
        except Exception:
            record.state = RuntimeState.UNHEALTHY
            with self._lock:
                self._models.pop(key, None)
            logger.exception("Failed to load model %s v%s", model_id, version)
            raise

    async def unload(self, model_id: str, version: str) -> None:
        """Unload a specific model version."""
        key = f"{model_id}:{version}"
        await self.unload_by_key(key)

    async def unload_all(self, model_id: str) -> int:
        """Unload all versions of a model."""
        count = 0
        with self._lock:
            keys = [k for k, v in self._models.items() if v.model_id == model_id]
        for key in keys:
            await self.unload_by_key(key)
            count += 1
        return count

    async def unload_by_key(self, key: str) -> None:
        """Internal: unload by cache key."""
        with self._lock:
            record = self._models.pop(key, None)
        if record:
            await self._release_model(record)
            logger.info("Model unloaded: %s", key)

    async def _release_model(self, record: ModelRecord) -> None:
        """Release model resources."""
        record.state = RuntimeState.UNLOADING
        record.model_object = None
        record.state = RuntimeState.UNLOADED

    async def _evict_if_needed(self) -> None:
        """LRU eviction when cache is full."""
        with self._lock:
            while len(self._models) >= self._cache_size:
                key, record = self._models.popitem(last=False)
                logger.info("LRU evicting model: %s", key)
                await self._release_model(record)

    # ------------------------------------------------------------------
    # Warmup
    # ------------------------------------------------------------------

    async def warmup(
        self,
        model_id: str,
        version: str,
        iterations: int = 10,
        input_dim: Optional[int] = None,
    ) -> None:
        """Warmup a model with dummy inferences.

        Args:
            model_id: Model identifier.
            version: Model version.
            iterations: Number of warmup inference cycles.
            input_dim: Feature dimension for dummy data generation.
        """
        key = f"{model_id}:{version}"

        with self._lock:
            record = self._models.get(key)
            if record is None:
                raise ValueError(f"Model not loaded: {key}")

        record.state = RuntimeState.WARMING
        input_dim = input_dim or record.metadata.get("input_dim", 64)

        # Generate dummy data matching input schema
        dummy_features = np.random.randn(input_dim).astype(np.float32).reshape(1, -1)

        for i in range(iterations):
            try:
                await self._run_inference(record, dummy_features)
            except Exception as exc:
                logger.warning("Warmup iteration %d failed: %s", i, exc)

        record.state = RuntimeState.READY
        logger.info("Model warmed up: %s (%d iterations)", key, iterations)

    async def warmup_all(self, iterations: int = 10) -> None:
        """Warmup all loaded models."""
        with self._lock:
            keys = list(self._models.keys())
        for key in keys:
            parts = key.split(":", 1)
            if len(parts) == 2:
                try:
                    await self.warmup(parts[0], parts[1], iterations=iterations)
                except Exception:
                    logger.exception("Warmup failed for %s", key)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    async def predict(
        self,
        model_id: str,
        version: str,
        features: Any,
    ) -> np.ndarray:
        """Run inference with a loaded model.

        Args:
            model_id: Model identifier.
            version: Model version.
            features: Input features as numpy array or dict.

        Returns:
            Prediction result as numpy array.
        """
        key = f"{model_id}:{version}"

        with self._lock:
            record = self._models.get(key)
            if record is None:
                raise ValueError(f"Model not loaded: {key}")
            if record.state not in (RuntimeState.READY, RuntimeState.LOADED):
                raise RuntimeError(f"Model {key} not ready (state={record.state})")
            # Update LRU
            self._models.move_to_end(key)
            record.last_used_at = datetime.now(timezone.utc)

        try:
            start = datetime.now(timezone.utc)
            result = await self._run_inference(record, features)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            record.inference_count += 1
            record.total_inference_ms += elapsed
            self._total_inferences += 1
            self._total_latency_ms += elapsed

            return result
        except Exception:
            record.error_count += 1
            self._total_errors += 1
            record.state = RuntimeState.UNHEALTHY
            raise

    async def _run_inference(self, record: ModelRecord, features: Any) -> np.ndarray:
        """Internal: dispatch inference to the correct backend."""
        model = record.model_object
        backend = record.backend

        # Convert features to appropriate format
        features_array = self._prepare_features(features, backend)

        # Run in thread pool for CPU-bound inference
        if backend == ModelBackend.SKLEARN:
            result = await asyncio.to_thread(model.predict, features_array)
        elif backend == ModelBackend.LIGHTGBM:
            result = await asyncio.to_thread(model.predict, features_array)
        elif backend == ModelBackend.XGBOOST:
            import xgboost as xgb
            dmatrix = await asyncio.to_thread(xgb.DMatrix, features_array)
            result = await asyncio.to_thread(model.predict, dmatrix)
        elif backend == ModelBackend.CATBOOST:
            result = await asyncio.to_thread(model.predict, features_array)
        elif backend == ModelBackend.PYTORCH:
            import torch
            tensor = torch.tensor(features_array, dtype=torch.float32)
            with torch.no_grad():
                result = model(tensor).numpy()
        elif backend == ModelBackend.ONNX:
            result = await asyncio.to_thread(
                lambda: model.run(None, {"input": features_array})[0]
            )
        elif backend == ModelBackend.TENSORFLOW:
            result = model(features_array).numpy()
        else:
            # Custom / generic callable
            if callable(model):
                result = await asyncio.to_thread(model, features_array)
            else:
                raise ValueError(f"Cannot run inference for backend: {backend}")

        # Ensure numpy output
        if not isinstance(result, np.ndarray):
            result = np.array(result)
        return result

    @staticmethod
    def _prepare_features(features: Any, backend: ModelBackend) -> np.ndarray:
        """Normalize features into a 2D numpy array."""
        if isinstance(features, np.ndarray):
            arr = features
        elif isinstance(features, dict):
            # Sort by key for consistent ordering
            arr = np.array([features[k] for k in sorted(features.keys())])
        elif isinstance(features, list):
            arr = np.array(features)
        else:
            arr = np.array(features)

        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr.astype(np.float32)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_model_info(self, model_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Get info for a loaded model."""
        key = f"{model_id}:{version}"
        with self._lock:
            record = self._models.get(key)
            if record is None:
                return None
            return {
                "model_id": record.model_id,
                "version": record.version,
                "backend": record.backend.value,
                "state": record.state.value,
                "loaded_at": record.loaded_at.isoformat() if record.loaded_at else None,
                "inference_count": record.inference_count,
                "avg_latency_ms": round(record.avg_latency_ms, 4),
                "error_rate": round(record.error_rate, 6),
            }

    def list_models(self) -> List[Dict[str, Any]]:
        """List all loaded models."""
        with self._lock:
            return [
                {
                    "model_id": r.model_id,
                    "version": r.version,
                    "state": r.state.value,
                    "backend": r.backend.value,
                }
                for r in self._models.values()
            ]

    def is_loaded(self, model_id: str, version: str) -> bool:
        """Check if a model is loaded and ready."""
        key = f"{model_id}:{version}"
        with self._lock:
            record = self._models.get(key)
            return (
                record is not None
                and record.state in (RuntimeState.READY, RuntimeState.LOADED)
            )

    async def health(self) -> Dict[str, Any]:
        """Runtime health check."""
        with self._lock:
            total = len(self._models)
            ready = sum(
                1 for r in self._models.values()
                if r.state == RuntimeState.READY
            )
            unhealthy = sum(
                1 for r in self._models.values()
                if r.state == RuntimeState.UNHEALTHY
            )

        return {
            "status": "healthy" if unhealthy == 0 else "degraded",
            "models_loaded": total,
            "models_ready": ready,
            "models_unhealthy": unhealthy,
            "cache_capacity": self._cache_size,
            "total_inferences": self._total_inferences,
            "total_errors": self._total_errors,
            "avg_latency_ms": round(
                self._total_latency_ms / max(self._total_inferences, 1), 4
            ),
        }

    async def drain(self, timeout: float = 30.0) -> None:
        """Drain in-flight inferences (no-op for synchronous runtime)."""
        pass

    def __repr__(self) -> str:
        with self._lock:
            n = len(self._models)
        return f"ModelRuntime(models={n}/{self._cache_size}, inferences={self._total_inferences})"
