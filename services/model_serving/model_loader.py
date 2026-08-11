"""
ICYQuant Model Loader — Responsible for loading model artifacts into runtime.

Handles artifact acquisition, deserialization, and warmup coordination.
Supports multiple backends and artifact storage locations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .model_repository import ModelRepository
    from .model_runtime import ModelRuntime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class LoadStrategy(str, Enum):
    """Model loading strategy."""
    EAGER = "eager"           # Load all at startup
    LAZY = "lazy"             # Load on first request
    PRELOAD = "preload"       # Load specified models, lazy for rest
    WARM_STANDBY = "warm_standby"  # Keep backup models warm


@dataclass
class LoadResult:
    """Result of a model load operation."""
    model_id: str
    version: str
    success: bool
    elapsed_ms: float
    error: Optional[str] = None
    loaded_at: Optional[datetime] = None


@dataclass
class LoadManifest:
    """Manifest specifying which models to load."""
    models: List[Dict[str, str]] = field(default_factory=list)
    strategy: LoadStrategy = LoadStrategy.EAGER
    warmup_iterations: int = 10
    parallel_loads: int = 4

    def add_model(self, model_id: str, version: str) -> None:
        self.models.append({"model_id": model_id, "version": version})


# ---------------------------------------------------------------------------
# Model Loader
# ---------------------------------------------------------------------------

class ModelLoader:
    """Loads model artifacts from repository into runtime.

    Responsibilities:
      - Resolve artifact paths from repository
      - Coordinate parallel model loading
      - Track loading progress
      - Handle load failures gracefully
      - Support warm standby models
    """

    def __init__(
        self,
        repository: "ModelRepository",
        runtime: Optional["ModelRuntime"] = None,
    ):
        self.repository = repository
        self.runtime = runtime
        self._initialized = False

        # Load history
        self._load_history: List[LoadResult] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("ModelLoader initialized")

    # ------------------------------------------------------------------
    # Load APIs
    # ------------------------------------------------------------------

    async def load_manifest(
        self,
        manifest: LoadManifest,
    ) -> List[LoadResult]:
        """Load all models specified in a manifest.

        Args:
            manifest: Loading specification.

        Returns:
            List of load results for each model.
        """
        if not self.runtime:
            raise RuntimeError("ModelLoader has no runtime reference")

        results: List[LoadResult] = []
        semaphore = asyncio.Semaphore(manifest.parallel_loads)

        async def load_one(spec: Dict[str, str]) -> LoadResult:
            async with semaphore:
                return await self.load_model(
                    model_id=spec["model_id"],
                    version=spec["version"],
                    warmup_iterations=manifest.warmup_iterations,
                )

        tasks = [load_one(spec) for spec in manifest.models]
        results = list(await asyncio.gather(*tasks))
        self._load_history.extend(results)

        success_count = sum(1 for r in results if r.success)
        logger.info(
            "Manifest loaded: %d/%d models succeeded (strategy=%s)",
            success_count, len(results), manifest.strategy.value,
        )

        return results

    async def load_model(
        self,
        model_id: str,
        version: str,
        warmup_iterations: int = 10,
    ) -> LoadResult:
        """Load a single model version.

        Workflow:
          1. Resolve artifact from repository
          2. Determine backend from metadata
          3. Load into runtime
          4. Optional warmup

        Args:
            model_id: Model identifier.
            version: Model version string.
            warmup_iterations: Number of warmup cycles.

        Returns:
            LoadResult indicating success/failure.
        """
        start = datetime.now(timezone.utc)

        try:
            # Stage 1: Resolve artifact
            artifact = await self.repository.get_artifact(model_id, version)
            if artifact is None:
                return LoadResult(
                    model_id=model_id,
                    version=version,
                    success=False,
                    elapsed_ms=0,
                    error=f"Artifact not found for {model_id}@{version}",
                )

            # Stage 2: Determine backend
            backend = artifact.get("backend", "sklearn")
            from .model_runtime import ModelBackend
            try:
                backend_enum = ModelBackend(backend)
            except ValueError:
                backend_enum = ModelBackend.CUSTOM

            # Stage 3: Load into runtime
            await self.runtime.load(
                model_id=model_id,
                version=version,
                backend=backend_enum,
                artifact_path=artifact.get("path"),
                metadata=artifact.get("metadata", {}),
            )

            # Stage 4: Warmup
            if warmup_iterations > 0:
                await self.runtime.warmup(
                    model_id=model_id,
                    version=version,
                    iterations=warmup_iterations,
                    input_dim=artifact.get("metadata", {}).get("input_dim"),
                )

            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            result = LoadResult(
                model_id=model_id,
                version=version,
                success=True,
                elapsed_ms=elapsed,
                loaded_at=datetime.now(timezone.utc),
            )
            logger.info("Loaded %s@%s in %.0fms", model_id, version, elapsed)
            return result

        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            result = LoadResult(
                model_id=model_id,
                version=version,
                success=False,
                elapsed_ms=elapsed,
                error=str(exc),
            )
            logger.error("Failed to load %s@%s: %s", model_id, version, exc)
            return result

    async def unload_model(self, model_id: str, version: str) -> bool:
        """Unload a model from runtime."""
        if not self.runtime:
            return False
        try:
            await self.runtime.unload(model_id, version)
            return True
        except Exception:
            logger.exception("Failed to unload %s@%s", model_id, version)
            return False

    async def reload_model(
        self,
        model_id: str,
        version: str,
        warmup_iterations: int = 10,
    ) -> LoadResult:
        """Hot-reload a model (unload then load)."""
        await self.unload_model(model_id, version)
        return await self.load_model(model_id, version, warmup_iterations)

    # ------------------------------------------------------------------
    # Preload & standby
    # ------------------------------------------------------------------

    async def preload_models(
        self,
        model_specs: List[Dict[str, str]],
        warmup_iterations: int = 10,
    ) -> List[LoadResult]:
        """Preload specified models ahead of requests."""
        manifest = LoadManifest(
            models=model_specs,
            strategy=LoadStrategy.PRELOAD,
            warmup_iterations=warmup_iterations,
        )
        return await self.load_manifest(manifest)

    async def maintain_warm_standby(
        self,
        model_id: str,
        standby_version: str,
    ) -> LoadResult:
        """Keep a standby model warm in memory."""
        return await self.load_model(
            model_id=model_id,
            version=standby_version,
            warmup_iterations=5,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_load_history(self) -> List[LoadResult]:
        """Get recent load history."""
        return list(self._load_history)

    def get_last_load(self, model_id: str, version: str) -> Optional[LoadResult]:
        """Get most recent load result for a model."""
        for result in reversed(self._load_history):
            if result.model_id == model_id and result.version == version:
                return result
        return None

    async def health(self) -> Dict[str, Any]:
        total = len(self._load_history)
        success = sum(1 for r in self._load_history if r.success)
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "total_loads": total,
            "successful_loads": success,
            "failed_loads": total - success,
            "last_load": (
                self._load_history[-1].model_id if self._load_history else None
            ),
        }

    def __repr__(self) -> str:
        return f"ModelLoader(loads={len(self._load_history)})"
