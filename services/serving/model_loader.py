"""Model Loader — unified model loading and hot reload.

Loads models from the Model Registry into memory for inference.
Supports LightGBM, XGBoost, CatBoost, ONNX (reserved), PyTorch (reserved).

Usage::

    loader = ModelLoader(registry=model_registry, storage=ml_storage)
    loaded = loader.load("alpha_model", version="v37")
    model = loaded.model  # ready for inference
"""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelFormat(str, Enum):
    """Supported model serialization formats."""
    LIGHTGBM = "LightGBM"
    XGBOOST = "XGBoost"
    CATBOOST = "CatBoost"
    ONNX = "ONNX"
    PYTORCH = "PyTorch"
    PICKLE = "Pickle"
    JOBLIB = "Joblib"
    UNKNOWN = "Unknown"


@dataclass
class LoadConfig:
    """Model loading configuration.

    Attributes:
        warmup: Whether to run warmup iterations after loading.
        warmup_samples: Number of warmup calls.
        preload_on_startup: Load all production models at startup.
        max_models_in_memory: Max concurrent models in memory.
        ttl_seconds: Idle model eviction time (0 = never).
        enable_lazy_loading: Load models on first use instead of eagerly.
    """

    warmup: bool = True
    warmup_samples: int = 10
    preload_on_startup: bool = True
    max_models_in_memory: int = 100
    ttl_seconds: int = 3600
    enable_lazy_loading: bool = False


@dataclass
class LoadedModel:
    """A model loaded into memory for inference.

    Attributes:
        model_name: Registry model name.
        version: Model version string.
        model: The actual model object ready for predict().
        format: Serialization format.
        framework: ML framework name.
        loaded_at: Timestamp when loaded.
        last_used_at: Last inference timestamp (for TTL eviction).
        metadata: Model metadata from registry.
        metrics: Training metrics from registry.
    """

    model_name: str
    version: str
    model: Any
    format: ModelFormat = ModelFormat.UNKNOWN
    framework: str = ""
    loaded_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.loaded_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used_at

    def touch(self) -> None:
        """Update last_used_at timestamp."""
        self.last_used_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "format": self.format.value,
            "framework": self.framework,
            "loaded_at": self.loaded_at,
            "age_seconds": round(self.age_seconds, 1),
            "idle_seconds": round(self.idle_seconds, 1),
            "metadata": self.metadata,
            "metrics": self.metrics,
        }


class ModelLoader:
    """Loads models from Model Registry and MLStorage into memory.

    Supports hot reload: when a new version is promoted to production,
    the loader can swap models without service restart.

    Usage::

        loader = ModelLoader(registry=model_registry, storage=ml_storage)
        model = loader.load("alpha_model")           # loads production version
        model = loader.load("alpha_model", "v38")     # loads specific version
        loader.reload("alpha_model")                  # hot-reload to latest production
        loader.unload("alpha_model", "v37")           # free memory
    """

    def __init__(
        self,
        registry: Any = None,
        storage: Any = None,
        config: Optional[LoadConfig] = None,
    ):
        self._registry = registry
        self._storage = storage
        self.config = config or LoadConfig()
        self._models: Dict[str, LoadedModel] = {}  # key = "model_name:version"
        self._active: Dict[str, str] = {}  # model_name → current version

    def load(self, model_name: str, version: Optional[str] = None) -> LoadedModel:
        """Load a model into memory.

        If version is None, loads the current production version from registry.
        """
        # Determine version
        if version is None:
            if self._registry:
                prod = self._registry.get_production(model_name)
                if prod:
                    version = prod.version
                else:
                    raise ValueError(f"No production version for '{model_name}'")
            else:
                raise ValueError("version required when no registry configured")

        key = f"{model_name}:{version}"

        # Return cached if already loaded
        if key in self._models:
            model = self._models[key]
            model.touch()
            return model

        # Load from storage
        if self._storage:
            artifact_path = f"models/{model_name}/{version}/model.pkl"
            try:
                raw = self._storage.load(artifact_path)
                loaded_model = self._deserialize(raw)
            except Exception:
                # Try alternate paths
                alt_paths = [
                    f"models/{model_name}_{version}.pkl",
                    f"models/{model_name}/model.pkl",
                ]
                loaded_model = None
                for path in alt_paths:
                    try:
                        raw = self._storage.load(path)
                        loaded_model = self._deserialize(raw)
                        break
                    except Exception:
                        continue
                if loaded_model is None:
                    raise FileNotFoundError(f"Model artifact not found for {model_name} v{version}")
        else:
            # No storage — create a mock for testing
            loaded_model = _MockModel(model_name, version)

        # Detect format and framework
        fmt = self._detect_format(loaded_model)
        framework = self._detect_framework(loaded_model)

        # Collect metadata from registry
        meta: Dict[str, Any] = {}
        metrics: Dict[str, float] = {}
        if self._registry:
            entry = self._registry.get(model_name)
            if entry:
                for v in entry.versions:
                    if v.version == version:
                        meta = v.metadata.to_dict() if v.metadata else {}
                        metrics = dict(v.metrics) if v.metrics else {}
                        break

        lm = LoadedModel(
            model_name=model_name,
            version=version,
            model=loaded_model,
            format=fmt,
            framework=framework,
            metadata=meta,
            metrics=metrics,
        )

        # Evict if at capacity
        if len(self._models) >= self.config.max_models_in_memory:
            self._evict_one()

        self._models[key] = lm
        self._active[model_name] = version

        return lm

    def reload(self, model_name: str) -> Optional[LoadedModel]:
        """Hot reload to latest production version.

        Unloads the old version and loads the new one atomically.
        Returns the new LoadedModel or None if already latest.
        """
        if not self._registry:
            raise RuntimeError("Registry required for reload")

        prod = self._registry.get_production(model_name)
        if prod is None:
            raise ValueError(f"No production version for '{model_name}'")

        current_version = self._active.get(model_name)

        if current_version == prod.version:
            return self._models.get(f"{model_name}:{current_version}")

        # Load new version
        new_model = self.load(model_name, prod.version)

        # Unload old version
        if current_version:
            old_key = f"{model_name}:{current_version}"
            self._models.pop(old_key, None)

        return new_model

    def unload(self, model_name: str, version: Optional[str] = None) -> bool:
        """Unload a model from memory.

        Args:
            model_name: Model to unload.
            version: Specific version. If None, unloads active version.

        Returns:
            True if model was unloaded.
        """
        if version is None:
            version = self._active.get(model_name)
            if version is None:
                return False

        key = f"{model_name}:{version}"
        if key in self._models:
            del self._models[key]
            if self._active.get(model_name) == version:
                del self._active[model_name]
            return True
        return False

    def get(self, model_name: str, version: Optional[str] = None) -> Optional[LoadedModel]:
        """Get a loaded model without triggering load."""
        if version:
            return self._models.get(f"{model_name}:{version}")
        active_ver = self._active.get(model_name)
        if active_ver:
            return self._models.get(f"{model_name}:{active_ver}")
        return None

    def list_loaded(self) -> List[LoadedModel]:
        """List all currently loaded models."""
        return list(self._models.values())

    def preload_all_production(self) -> List[LoadedModel]:
        """Preload all production models from registry."""
        if not self._registry:
            return []
        loaded = []
        for entry in self._registry.list_models():
            try:
                lm = self.load(entry.model_name)
                loaded.append(lm)
            except Exception:
                continue
        return loaded

    def evict_idle(self, max_idle_seconds: int = 3600) -> int:
        """Evict models idle longer than max_idle_seconds."""
        to_remove = []
        now = time.time()
        for key, lm in self._models.items():
            if (now - lm.last_used_at) > max_idle_seconds:
                to_remove.append(key)

        for key in to_remove:
            del self._models[key]
            name = key.rsplit(":", 1)[0]
            if self._active.get(name):
                del self._active[name]

        return len(to_remove)

    # ---- internal ----

    def _deserialize(self, raw: bytes) -> Any:
        """Deserialize model from bytes."""
        try:
            return pickle.loads(raw)
        except Exception:
            raise ValueError("Failed to deserialize model")

    def _detect_format(self, model: Any) -> ModelFormat:
        """Detect serialization format from model type."""
        module = type(model).__module__
        class_name = type(model).__name__

        if "lightgbm" in module.lower() or class_name == "Booster":
            return ModelFormat.LIGHTGBM
        if "xgboost" in module.lower() or class_name == "Booster":
            return ModelFormat.XGBOOST
        if "catboost" in module.lower():
            return ModelFormat.CATBOOST
        if "onnx" in module.lower():
            return ModelFormat.ONNX
        if "torch" in module.lower():
            return ModelFormat.PYTORCH
        if class_name == "MockModel":
            return ModelFormat.PICKLE
        return ModelFormat.PICKLE

    def _detect_framework(self, model: Any) -> str:
        """Detect ML framework from model type."""
        module = type(model).__module__.lower()
        for fw in ["lightgbm", "xgboost", "catboost", "onnx", "torch", "tensorflow", "sklearn"]:
            if fw in module:
                return fw
        return "unknown"

    def _evict_one(self) -> None:
        """Evict the least recently used model."""
        if not self._models:
            return
        oldest_key = min(self._models, key=lambda k: self._models[k].last_used_at)
        del self._models[oldest_key]


class _MockModel:
    """Mock model for testing without actual model files."""

    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.feature_names_ = None

    def predict(self, features):
        """Return a mock prediction."""
        if isinstance(features, dict):
            return 0.75
        import numpy as np
        if hasattr(features, 'shape'):
            return np.full(features.shape[0], 0.75)
        return 0.75

    def predict_proba(self, features):
        """Return mock probabilities."""
        import numpy as np
        if isinstance(features, dict):
            return np.array([[0.2, 0.8]])
        n = features.shape[0] if hasattr(features, 'shape') else 1
        return np.column_stack([np.full(n, 0.2), np.full(n, 0.8)])
