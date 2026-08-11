"""
ICYQuant Deployment Manager — Orchestrates model deployments.

Manages the full deployment lifecycle:
  - Deployment creation and state transitions
  - Canary rollout with progressive traffic shifting
  - Shadow deployment evaluation
  - Automatic rollback on threshold breach
  - Multi-version coexistence
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .model_deployment import (
    ModelDeployment,
    DeploymentState,
    DeploymentEvent,
    DeploymentConfig,
)

if TYPE_CHECKING:
    from .model_runtime import ModelRuntime
    from .model_repository import ModelRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deployment Manager
# ---------------------------------------------------------------------------

class DeploymentManager:
    """Orchestrates model deployments across lifecycle.

    Responsibilities:
      - Create and track deployments per model_id
      - Enforce valid state transitions
      - Manage canary traffic allocation
      - Coordinate shadow deployments
      - Automatic rollback logic
      - Provide deployment history

    Usage::

        manager = DeploymentManager(runtime, repository)
        await manager.initialize()
        dep = await manager.deploy("nvda_model", "v1.5")
        await manager.start_canary("nvda_model", "v1.6", traffic_percent=5.0)
    """

    def __init__(
        self,
        runtime: "ModelRuntime",
        repository: "ModelRepository",
    ):
        self.runtime = runtime
        self.repository = repository

        # model_id → list of deployments (ordered by creation)
        self._deployments: Dict[str, List[ModelDeployment]] = defaultdict(list)

        # deployment_id → ModelDeployment
        self._by_id: Dict[str, ModelDeployment] = {}

        # model_id → production deployment
        self._production: Dict[str, ModelDeployment] = {}

        # model_id → canary deployment
        self._canaries: Dict[str, ModelDeployment] = {}

        # model_id → shadow deployment
        self._shadows: Dict[str, ModelDeployment] = {}

        self._initialized = False

        # Rollback tracking
        self._rollback_lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("DeploymentManager initialized")

    async def shutdown(self) -> None:
        self._initialized = False

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    async def deploy(
        self,
        model_id: str,
        version: str,
        config: Optional[DeploymentConfig] = None,
        target_state: DeploymentState = DeploymentState.PRODUCTION,
    ) -> ModelDeployment:
        """Deploy a model version.

        Steps:
          1. Create deployment record
          2. Load model into runtime
          3. Transition to target state
          4. Update production pointer (if target is PRODUCTION)

        Args:
            model_id: Model identifier.
            version: Model version to deploy.
            config: Deployment configuration.
            target_state: Target deployment state.

        Returns:
            The created deployment.
        """
        # Verify artifact exists
        artifact = await self.repository.get_artifact(model_id, version)
        if artifact is None:
            raise ValueError(f"Artifact not found: {model_id}@{version}")

        # Create deployment record
        dep_id = str(uuid.uuid4())
        deployment = ModelDeployment(
            deployment_id=dep_id,
            model_id=model_id,
            version=version,
            config=config or DeploymentConfig(),
        )

        # Load model into runtime
        await self._ensure_loaded(model_id, version, artifact)

        # Track previous production version
        prev_prod = self._production.get(model_id)
        if prev_prod:
            deployment.previous_version = prev_prod.version
            deployment.previous_deployment_id = prev_prod.deployment_id

        # Register
        deployment.transition(DeploymentEvent.REGISTER)

        self._deployments[model_id].append(deployment)
        self._by_id[dep_id] = deployment

        # Progress to target state
        await self._progress_to_target(deployment, target_state)

        # Update production pointer
        if target_state == DeploymentState.PRODUCTION:
            await self._set_production(model_id, deployment)

        logger.info(
            "Deployed %s@%s → %s (dep_id=%s)",
            model_id, version, target_state.value, dep_id[:8],
        )

        return deployment

    async def rollback(self, model_id: str) -> ModelDeployment:
        """Rollback to previous production version.

        Returns:
            The newly activated deployment.
        """
        current = self._production.get(model_id)
        if current is None:
            raise ValueError(f"No production deployment for {model_id}")

        prev_version = current.previous_version
        if prev_version is None:
            raise ValueError(f"No previous version to rollback for {model_id}")

        logger.warning("Rolling back %s: %s → %s", model_id, current.version, prev_version)

        async with self._rollback_lock:
            # Mark current as rollback
            current.rollback(f"Rolling back to {prev_version}")

            # Deploy previous version as production
            deployment = await self.deploy(
                model_id=model_id,
                version=prev_version,
                target_state=DeploymentState.PRODUCTION,
            )

            return deployment

    # ------------------------------------------------------------------
    # Canary
    # ------------------------------------------------------------------

    async def start_canary(
        self,
        model_id: str,
        candidate_version: str,
        traffic_percent: float = 5.0,
    ) -> ModelDeployment:
        """Start a canary deployment with gradual traffic.

        Args:
            model_id: Model identifier.
            candidate_version: Candidate model version.
            traffic_percent: Initial traffic percentage (1-50).

        Returns:
            Canary deployment.
        """
        if not 1.0 <= traffic_percent <= 50.0:
            raise ValueError("Canary traffic percent must be between 1 and 50")

        # Check existing canary
        if model_id in self._canaries:
            raise ValueError(f"Canary already active for {model_id}")

        config = DeploymentConfig(canary_traffic_percent=traffic_percent)

        deployment = await self.deploy(
            model_id=model_id,
            version=candidate_version,
            config=config,
            target_state=DeploymentState.CANARY,
        )

        self._canaries[model_id] = deployment
        logger.info(
            "Canary started: %s@%s (%.1f%% traffic)",
            model_id, candidate_version, traffic_percent,
        )

        return deployment

    async def update_canary_traffic(
        self,
        model_id: str,
        traffic_percent: float,
    ) -> Optional[ModelDeployment]:
        """Adjust canary traffic allocation."""
        deployment = self._canaries.get(model_id)
        if deployment is None:
            raise ValueError(f"No active canary for {model_id}")

        if not 1.0 <= traffic_percent <= 100.0:
            raise ValueError("Traffic percent must be between 1 and 100")

        deployment.config.canary_traffic_percent = traffic_percent
        logger.info(
            "Canary traffic updated: %s → %.1f%%", model_id, traffic_percent
        )
        return deployment

    async def promote_canary(self, model_id: str) -> ModelDeployment:
        """Promote a successful canary to full production.

        This transitions canary → production and archives previous production.
        """
        canary = self._canaries.pop(model_id, None)
        if canary is None:
            raise ValueError(f"No active canary for {model_id}")

        # Progress to production
        await self._progress_to_target(canary, DeploymentState.PRODUCTION)
        await self._set_production(model_id, canary)

        # Archive previous production
        prev = self._production.get(model_id)
        # (prev is now canary since _set_production updated it)

        logger.info(
            "Canary promoted: %s@%s → PRODUCTION",
            model_id, canary.version,
        )

        return canary

    async def abort_canary(self, model_id: str) -> ModelDeployment:
        """Abort canary deployment — unload and remove."""
        canary = self._canaries.pop(model_id, None)
        if canary is None:
            raise ValueError(f"No active canary for {model_id}")

        canary.rollback("Canary aborted")
        await self.runtime.unload(model_id, canary.version)

        logger.info("Canary aborted: %s@%s", model_id, canary.version)
        return canary

    # ------------------------------------------------------------------
    # Shadow
    # ------------------------------------------------------------------

    async def start_shadow(
        self,
        model_id: str,
        candidate_version: str,
    ) -> ModelDeployment:
        """Start shadow deployment — evaluate without affecting live traffic.

        The shadow model receives the same inputs as production but its
        predictions are only logged for comparison, not used for decisions.
        """
        if model_id in self._shadows:
            raise ValueError(f"Shadow deployment already active for {model_id}")

        artifact = await self.repository.get_artifact(model_id, candidate_version)
        if artifact is None:
            raise ValueError(f"Artifact not found: {model_id}@{candidate_version}")

        await self._ensure_loaded(model_id, candidate_version, artifact)

        dep_id = str(uuid.uuid4())
        deployment = ModelDeployment(
            deployment_id=dep_id,
            model_id=model_id,
            version=candidate_version,
            state=DeploymentState.STAGING,
        )
        deployment.transition(DeploymentEvent.REGISTER)

        self._deployments[model_id].append(deployment)
        self._by_id[dep_id] = deployment
        self._shadows[model_id] = deployment

        logger.info("Shadow started: %s@%s", model_id, candidate_version)
        return deployment

    async def stop_shadow(self, model_id: str) -> Optional[ModelDeployment]:
        """Stop shadow deployment."""
        shadow = self._shadows.pop(model_id, None)
        if shadow:
            await self.runtime.unload(model_id, shadow.version)
            shadow.archive()
            logger.info("Shadow stopped: %s@%s", model_id, shadow.version)
        return shadow

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_production(self, model_id: str) -> Optional[ModelDeployment]:
        """Get current production deployment."""
        return self._production.get(model_id)

    def get_canary(self, model_id: str) -> Optional[ModelDeployment]:
        """Get active canary deployment."""
        return self._canaries.get(model_id)

    def get_shadow(self, model_id: str) -> Optional[ModelDeployment]:
        """Get active shadow deployment."""
        return self._shadows.get(model_id)

    def get_deployment(self, deployment_id: str) -> Optional[ModelDeployment]:
        """Get deployment by ID."""
        return self._by_id.get(deployment_id)

    def list_deployments(self, model_id: str) -> List[ModelDeployment]:
        """List all deployments for a model."""
        return self._deployments.get(model_id, [])

    def get_deployment_history(self, model_id: str) -> List[Dict[str, Any]]:
        """Get deployment history as dicts."""
        return [d.to_dict() for d in self.list_deployments(model_id)]

    def get_traffic_allocation(self, model_id: str) -> Dict[str, Any]:
        """Get current traffic allocation for a model.

        Returns:
            Dict with production/canary/shadow traffic splits.
        """
        result: Dict[str, Any] = {
            "model_id": model_id,
            "production": None,
            "canary": None,
            "shadow": None,
        }

        prod = self._production.get(model_id)
        if prod:
            result["production"] = {
                "version": prod.version,
                "deployment_id": prod.deployment_id,
                "traffic_percent": (
                    100.0 - self._canary_traffic(model_id)
                ),
            }

        canary = self._canaries.get(model_id)
        if canary:
            result["canary"] = {
                "version": canary.version,
                "deployment_id": canary.deployment_id,
                "traffic_percent": canary.config.canary_traffic_percent,
            }

        shadow = self._shadows.get(model_id)
        if shadow:
            result["shadow"] = {
                "version": shadow.version,
                "deployment_id": shadow.deployment_id,
            }

        return result

    # ------------------------------------------------------------------
    # Auto-rollback
    # ------------------------------------------------------------------

    async def check_rollback_conditions(self, model_id: str) -> bool:
        """Evaluate rollback thresholds and perform rollback if needed.

        Returns:
            True if rollback occurred.
        """
        deployment = self._production.get(model_id)
        if deployment is None:
            return False

        if not deployment.config.auto_rollback:
            return False

        # Placeholder — actual monitoring integration would provide metrics
        # In production, this would check: error_rate, latency_p99, drift_score

        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ensure_loaded(
        self, model_id: str, version: str, artifact: Dict[str, Any]
    ) -> None:
        """Ensure model is loaded in runtime."""
        if not self.runtime.is_loaded(model_id, version):
            from .model_runtime import ModelBackend
            from .model_loader import ModelLoader

            backend = artifact.get("backend", "sklearn")
            try:
                backend_enum = ModelBackend(backend)
            except ValueError:
                backend_enum = ModelBackend.CUSTOM

            await self.runtime.load(
                model_id=model_id,
                version=version,
                backend=backend_enum,
                artifact_path=artifact.get("path"),
                metadata=artifact.get("metadata", {}),
            )

    async def _progress_to_target(
        self,
        deployment: ModelDeployment,
        target: DeploymentState,
    ) -> None:
        """Progress deployment through states to reach target."""
        state_order = [
            DeploymentState.REGISTERED,
            DeploymentState.VALIDATED,
            DeploymentState.CANDIDATE,
            DeploymentState.STAGING,
            DeploymentState.CANARY,
            DeploymentState.PRODUCTION,
        ]

        try:
            start_idx = state_order.index(deployment.state)
            target_idx = state_order.index(target)
        except ValueError:
            return

        for i in range(start_idx + 1, target_idx + 1):
            next_state = state_order[i]
            if next_state == DeploymentState.VALIDATED:
                deployment.validate()
            elif next_state == DeploymentState.CANDIDATE:
                deployment.promote_to_candidate()
            elif next_state == DeploymentState.STAGING:
                deployment.promote_to_staging()
            elif next_state == DeploymentState.CANARY:
                deployment.start_canary()
            elif next_state == DeploymentState.PRODUCTION:
                deployment.promote_to_production()

    async def _set_production(
        self, model_id: str, deployment: ModelDeployment
    ) -> None:
        """Set production deployment — archive previous."""
        prev = self._production.get(model_id)
        if prev and prev.deployment_id != deployment.deployment_id:
            try:
                prev.archive()
            except ValueError:
                pass  # May already be in terminal state

        self._production[model_id] = deployment

    def _canary_traffic(self, model_id: str) -> float:
        """Get canary traffic percentage for a model."""
        canary = self._canaries.get(model_id)
        return canary.config.canary_traffic_percent if canary else 0.0

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_deployments": len(self._by_id),
            "production_models": len(self._production),
            "canary_models": len(self._canaries),
            "shadow_models": len(self._shadows),
            "production_versions": {
                m: d.version for m, d in self._production.items()
            },
        }

    def __repr__(self) -> str:
        return (
            f"DeploymentManager(prod={len(self._production)}, "
            f"canary={len(self._canaries)}, shadow={len(self._shadows)})"
        )
