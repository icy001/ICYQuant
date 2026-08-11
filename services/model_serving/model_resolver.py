"""
ICYQuant Model Resolver — Resolves model_id to specific version and artifact.

Handles:
  - Default-version resolution (production, staging, latest)
  - Aliased model resolution (friendly names → model_id)
  - Version constraint parsing (>=, ~=, exact)
  - Deployment-stage-aware resolution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .model_repository import ModelRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Stage(str, Enum):
    """Model deployment stages."""
    PRODUCTION = "production"
    STAGING = "staging"
    CANARY = "canary"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    TRAINING = "training"
    ARCHIVED = "archived"


class ResolutionStrategy(str, Enum):
    """How to resolve a model version."""
    PRODUCTION = "production"       # Always the active production version
    STAGING = "staging"             # The staging version (pre-production)
    LATEST = "latest"               # Most recently registered version
    PINNED = "pinned"               # Exact version specified
    CANDIDATE = "candidate"          # Latest candidate for promotion
    CANARY = "canary"               # Current canary version


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ModelAlias:
    """Maps a friendly alias to a concrete model_id."""
    alias: str
    model_id: str
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        return {
            "alias": self.alias,
            "model_id": self.model_id,
            "description": self.description,
        }


@dataclass
class ResolutionResult:
    """Result of model ID / version resolution."""
    model_id: str
    version: str
    strategy: ResolutionStrategy
    stage: Stage = Stage.PRODUCTION
    artifact_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "strategy": self.strategy.value,
            "stage": self.stage.value,
            "artifact_path": self.artifact_path,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Model Resolver
# ---------------------------------------------------------------------------

class ModelResolver:
    """Resolves model_id + constraints → concrete version + artifact.

    Usage::

        resolver = ModelResolver(repository)
        prod = await resolver.resolve("nvda_alpha_model")
        pinned = await resolver.resolve("nvda_alpha_model:v2.1")
        staging = await resolver.resolve("nvda_alpha_model", strategy=ResolutionStrategy.STAGING)
    """

    def __init__(
        self,
        repository: "ModelRepository",
        aliases: Optional[Dict[str, str]] = None,
    ):
        self.repository = repository
        self._aliases: Dict[str, str] = aliases or {}

        # Per-model stage → version mapping
        self._stage_map: Dict[str, Dict[str, str]] = {}

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize — load existing stage mappings."""
        self._initialized = True
        logger.info("ModelResolver initialized — %d aliases", len(self._aliases))

    # ------------------------------------------------------------------
    # Alias management
    # ------------------------------------------------------------------

    def register_alias(self, alias: str, model_id: str) -> None:
        """Register a friendly alias."""
        self._aliases[alias] = model_id
        logger.info("Alias registered: %s → %s", alias, model_id)

    def unregister_alias(self, alias: str) -> None:
        """Remove an alias."""
        self._aliases.pop(alias, None)

    def resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to its concrete model_id."""
        return self._aliases.get(alias)

    def list_aliases(self) -> Dict[str, str]:
        """List all registered aliases."""
        return dict(self._aliases)

    # ------------------------------------------------------------------
    # Stage management
    # ------------------------------------------------------------------

    def set_stage(self, model_id: str, stage: Stage, version: str) -> None:
        """Set a model version's deployment stage."""
        if model_id not in self._stage_map:
            self._stage_map[model_id] = {}
        self._stage_map[model_id][stage.value] = version
        logger.info("Stage set: %s → %s = %s", model_id, stage.value, version)

    def get_stage(self, model_id: str, stage: Stage) -> Optional[str]:
        """Get the version assigned to a stage."""
        return self._stage_map.get(model_id, {}).get(stage.value)

    def promote_stage(self, model_id: str, version: str, to_stage: Stage) -> None:
        """Promote a model version to a new stage."""
        self.set_stage(model_id, to_stage, version)

    def list_stages(self, model_id: str) -> Dict[str, str]:
        """List all stage assignments for a model."""
        return self._stage_map.get(model_id, {})

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        model_ref: str,
        *,
        strategy: Optional[ResolutionStrategy] = None,
        stage: Optional[Stage] = None,
    ) -> ResolutionResult:
        """Resolve a model reference to concrete model_id + version.

        Resolution rules (in order):
          1. Parse explicit version from model_ref (e.g., 'model_id:v2.1')
          2. Apply resolution strategy (production, staging, latest, etc.)
          3. Check stage assignments
          4. Fallback to repository latest

        Args:
            model_ref: Model reference — can be 'model_id', 'model_id:version', or alias.
            strategy: Resolution strategy. Defaults to PRODUCTION.
            stage: Optional explicit stage override.

        Returns:
            ResolutionResult with concrete model_id and version.

        Raises:
            ValueError: If model cannot be resolved.
        """
        # Step 1: Parse explicit version
        model_id, explicit_version = self._parse_model_ref(model_ref)

        # Step 2: Resolve alias
        resolved_id = self._aliases.get(model_id, model_id)

        # Step 3: If explicit version, return immediately
        if explicit_version:
            return await self._resolve_explicit(resolved_id, explicit_version)

        # Step 4: Determine resolution strategy
        if strategy is None:
            if stage:
                strategy = self._stage_to_strategy(stage)
            else:
                strategy = ResolutionStrategy.PRODUCTION

        # Step 5: Resolve by strategy
        version = await self._resolve_by_strategy(resolved_id, strategy)
        if version is None:
            # Fallback: use latest from repository
            version = await self.repository.get_latest_version(resolved_id)
            if version is None:
                raise ValueError(
                    f"Cannot resolve model: {model_ref} "
                    f"(no versions found for {resolved_id})"
                )
            strategy = ResolutionStrategy.LATEST

        # Step 6: Get artifact path
        artifact = await self.repository.get_artifact(resolved_id, version)

        return ResolutionResult(
            model_id=resolved_id,
            version=version,
            strategy=strategy,
            stage=stage or self._strategy_to_stage(strategy),
            artifact_path=artifact.get("path") if artifact else None,
            metadata=artifact.get("metadata", {}) if artifact else {},
        )

    async def resolve_production_models(self) -> List[Dict[str, str]]:
        """Resolve all models that have a production version.

        Returns:
            List of {model_id, version} dicts.
        """
        models: List[Dict[str, str]] = []

        # Check stage map
        for model_id, stages in self._stage_map.items():
            if "production" in stages:
                models.append({
                    "model_id": model_id,
                    "version": stages["production"],
                })

        # Also check all models in repository
        all_models = await self.repository.list_models()
        for model_id in all_models:
            if model_id not in self._stage_map:
                versions = await self.repository.list_versions(model_id)
                if versions:
                    models.append({
                        "model_id": model_id,
                        "version": versions[-1],  # Latest as production default
                    })

        return models

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_model_ref(model_ref: str) -> Tuple[str, Optional[str]]:
        """Parse 'model_id:version' or 'model_id' format."""
        if ":" in model_ref:
            parts = model_ref.rsplit(":", 1)
            return parts[0], parts[1]
        return model_ref, None

    async def _resolve_explicit(
        self, model_id: str, version: str
    ) -> ResolutionResult:
        """Resolve when version is explicitly provided."""
        # Check version constraints
        if version.startswith(">="):
            min_version = version[2:]
            versions = await self.repository.list_versions(model_id)
            candidates = [v for v in versions if v >= min_version]
            if not candidates:
                raise ValueError(f"No version >= {min_version} for {model_id}")
            version = candidates[-1]
        elif version == "latest":
            version = await self.repository.get_latest_version(model_id) or version

        artifact = await self.repository.get_artifact(model_id, version)

        return ResolutionResult(
            model_id=model_id,
            version=version,
            strategy=ResolutionStrategy.PINNED,
            stage=Stage.PRODUCTION,
            artifact_path=artifact.get("path") if artifact else None,
            metadata=artifact.get("metadata", {}) if artifact else {},
        )

    async def _resolve_by_strategy(
        self, model_id: str, strategy: ResolutionStrategy
    ) -> Optional[str]:
        """Resolve version based on strategy."""
        # Check stage map first
        stage_value = self._strategy_to_stage(strategy)
        stage_version = self.get_stage(model_id, stage_value)
        if stage_version:
            return stage_version

        # Repository-based resolution
        if strategy == ResolutionStrategy.LATEST:
            return await self.repository.get_latest_version(model_id)

        if strategy == ResolutionStrategy.PINNED:
            return None  # Requires explicit version

        # Default: latest
        return await self.repository.get_latest_version(model_id)

    @staticmethod
    def _strategy_to_stage(strategy: ResolutionStrategy) -> Stage:
        """Map resolution strategy to deployment stage."""
        mapping = {
            ResolutionStrategy.PRODUCTION: Stage.PRODUCTION,
            ResolutionStrategy.STAGING: Stage.STAGING,
            ResolutionStrategy.CANARY: Stage.CANARY,
            ResolutionStrategy.CANDIDATE: Stage.CANDIDATE,
            ResolutionStrategy.LATEST: Stage.PRODUCTION,
            ResolutionStrategy.PINNED: Stage.PRODUCTION,
        }
        return mapping[strategy]

    @staticmethod
    def _stage_to_strategy(stage: Stage) -> ResolutionStrategy:
        """Map deployment stage to resolution strategy."""
        mapping = {
            Stage.PRODUCTION: ResolutionStrategy.PRODUCTION,
            Stage.STAGING: ResolutionStrategy.STAGING,
            Stage.CANARY: ResolutionStrategy.CANARY,
            Stage.CANDIDATE: ResolutionStrategy.CANDIDATE,
            Stage.VALIDATED: ResolutionStrategy.LATEST,
            Stage.TRAINING: ResolutionStrategy.LATEST,
            Stage.ARCHIVED: ResolutionStrategy.LATEST,
        }
        return mapping[stage]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "aliases_count": len(self._aliases),
            "stage_models": len(self._stage_map),
            "aliases": dict(self._aliases),
        }

    def __repr__(self) -> str:
        return (
            f"ModelResolver(aliases={len(self._aliases)}, "
            f"stage_models={len(self._stage_map)})"
        )
