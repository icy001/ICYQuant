"""
Unified Strategy Engine — top-level entry point for the Production Strategy Platform.

Orchestrates the full strategy lifecycle pipeline:
    Load → Validate → Deploy → Run → Snapshot → Recovery

The StrategyEngine composes all subsystems (registry, loader, validator,
runtime, scheduler, snapshot, recovery) behind a single async interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .strategy_lifecycle import StrategyLifecycleManager, StateTransition
from .strategy_loader import StrategyLoader, PackageSource
from .strategy_manager import StrategyManager
from .strategy_package import StrategyPackage
from .strategy_recovery import StrategyRecovery
from .strategy_registry import StrategyRegistry
from .strategy_repository import StrategyRepository
from .strategy_runtime import StrategyRuntime
from .strategy_scheduler import StrategyScheduler
from .strategy_snapshot import SnapshotManager
from .strategy_state import StrategyLifecycleState, ACTIVE_STATES
from .strategy_validator import StrategyValidator, ValidationResult

logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    """Engine operational state."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class DeployRequest:
    """Request to deploy a strategy."""
    source: PackageSource
    config: Dict[str, Any] = field(default_factory=dict)
    strategy_id: str = ""
    deploy_mode: str = "production"  # production, staging, paper
    force: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployResult:
    """Result of a strategy deployment."""
    success: bool
    strategy_id: str = ""
    version: str = ""
    state: StrategyLifecycleState = StrategyLifecycleState.CREATED
    validation: Optional[ValidationResult] = None
    error: str = ""
    deploy_time_ms: float = 0.0


@dataclass
class OperationResult:
    """Generic strategy operation result."""
    success: bool
    strategy_id: str
    action: str
    previous_state: Optional[StrategyLifecycleState] = None
    new_state: Optional[StrategyLifecycleState] = None
    message: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyEngine:
    """Unified entry point for the Production Strategy Platform.

    Composes all strategy subsystems into a single lifecycle pipeline:

        ┌──────────────────────────────────────┐
        │          StrategyEngine              │
        │                                      │
        │  deploy()                            │
        │    ├── load          (Loader)        │
        │    ├── validate      (Validator)     │
        │    ├── register      (Registry)      │
        │    ├── prepare       (Runtime)       │
        │    └── start         (Runtime)       │
        │                                      │
        │  start() / stop() / pause() / resume │
        │                                      │
        │  snapshot() / recover()              │
        └──────────────────────────────────────┘

    Usage:
        engine = StrategyEngine()
        await engine.initialize()

        # Deploy a strategy
        result = await engine.deploy(DeployRequest(
            source=PackageSource(format=PackageFormat.LOCAL, location="./my_strategy"),
        ))

        # Manage lifecycle
        await engine.start(result.strategy_id)
        await engine.stop(result.strategy_id)

        await engine.shutdown()
    """

    def __init__(self) -> None:
        # Sub-systems
        self.loader = StrategyLoader()
        self.validator = StrategyValidator()
        self.registry = StrategyRegistry()
        self.repository = StrategyRepository()
        self.runtime = StrategyRuntime()
        self.scheduler = StrategyScheduler()
        self.lifecycle = StrategyLifecycleManager()
        self.snapshot_manager = SnapshotManager()
        self.recovery = StrategyRecovery()
        self.manager = StrategyManager()

        self._state: EngineState = EngineState.UNINITIALIZED
        self._deployment_log: List[Dict[str, Any]] = []
        logger.info("StrategyEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize all strategy subsystems."""
        if self._state != EngineState.UNINITIALIZED:
            logger.warning("Engine already initialized (state=%s)", self._state.value)
            return

        self._state = EngineState.INITIALIZING
        logger.info("Initializing StrategyEngine subsystems...")

        subsystems = [
            ("repository", self.repository),
            ("loader", self.loader),
            ("validator", self.validator),
            ("registry", self.registry),
            ("manager", self.manager),
            ("lifecycle", self.lifecycle),
            ("runtime", self.runtime),
            ("scheduler", self.scheduler),
            ("snapshot_manager", self.snapshot_manager),
            ("recovery", self.recovery),
        ]

        for name, sub in subsystems:
            try:
                await sub.initialize()
                logger.debug("  %s initialized", name)
            except Exception as e:
                logger.error("  %s failed: %s", name, e)
                self._state = EngineState.DEGRADED
                raise

        # Wire manager dependencies
        self.manager.registry = self.registry
        self.manager.repository = self.repository
        self.manager.runtime = self.runtime
        self.manager.scheduler = self.scheduler
        self.manager.loader = self.loader
        self.manager.snapshot_manager = self.snapshot_manager
        await self.manager._init_dependencies()

        self._state = EngineState.READY
        logger.info("StrategyEngine initialized — state=READY")

    async def shutdown(self) -> None:
        """Gracefully shut down the entire strategy platform."""
        self._state = EngineState.SHUTTING_DOWN
        logger.info("Shutting down StrategyEngine...")

        subsystems = [
            ("manager", self.manager),
            ("scheduler", self.scheduler),
            ("runtime", self.runtime),
            ("snapshot_manager", self.snapshot_manager),
            ("recovery", self.recovery),
            ("lifecycle", self.lifecycle),
            ("registry", self.registry),
            ("validator", self.validator),
            ("loader", self.loader),
            ("repository", self.repository),
        ]

        for name, sub in subsystems:
            try:
                await sub.shutdown()
                logger.debug("  %s shut down", name)
            except Exception as e:
                logger.error("  %s shutdown error: %s", name, e)

        self._state = EngineState.STOPPED
        logger.info("StrategyEngine shut down")

    # ── Deploy ──

    async def deploy(self, request: DeployRequest) -> DeployResult:
        """Full strategy deployment pipeline.

        Pipeline:
            1. LOAD    — load the strategy package
            2. VALIDATE — run validation checks
            3. REGISTER — register in the platform
            4. PREPARE  — allocate runtime slot
            5. START    — begin execution (optional)
        """
        t_start = datetime.now(timezone.utc)
        logger.info("Deploy requested: source=%s", request.source.location)

        # 1. Load
        try:
            package = await self.loader.load(request.source)
        except Exception as e:
            return DeployResult(success=False, error=f"Load failed: {e}",
                                deploy_time_ms=self._elapsed_ms(t_start))

        strategy_id = request.strategy_id or f"{package.manifest.name}@v{package.manifest.version}"
        logger.info("Step 1/5 LOADED: %s", strategy_id)

        # 2. Validate
        config = request.config
        validation = await self.validator.validate(
            manifest=package.manifest,
            config=config,
            strategy_id=strategy_id,
        )
        if not validation.is_valid and not request.force:
            return DeployResult(
                success=False, strategy_id=strategy_id,
                version=package.manifest.version,
                validation=validation,
                error="Validation failed. Use force=True to skip.",
                deploy_time_ms=self._elapsed_ms(t_start),
            )
        logger.info("Step 2/5 VALIDATED: %s (valid=%s)", strategy_id, validation.is_valid)

        # 3. Register
        try:
            self.registry.register(strategy_id, package.manifest)
            self.registry.update_state(strategy_id, StrategyLifecycleState.VALIDATED, "Deployment validation passed")
        except Exception as e:
            return DeployResult(success=False, strategy_id=strategy_id,
                                error=f"Registration failed: {e}",
                                deploy_time_ms=self._elapsed_ms(t_start))
        logger.info("Step 3/5 REGISTERED: %s", strategy_id)

        # Persist
        await self.repository.save_manifest(package.manifest)
        metadata = self.registry.get_metadata(strategy_id)
        if metadata:
            await self.repository.save_metadata(metadata)

        # 4. Prepare runtime
        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.DEPLOYING, "Runtime preparation")
            await self.runtime.prepare(strategy_id, package, config=config)
            self.registry.update_state(strategy_id, StrategyLifecycleState.DEPLOYED, "Runtime ready")
        except Exception as e:
            self.registry.update_state(strategy_id, StrategyLifecycleState.FAILED, f"Runtime preparation failed: {e}")
            return DeployResult(success=False, strategy_id=strategy_id,
                                error=f"Runtime prep failed: {e}",
                                deploy_time_ms=self._elapsed_ms(t_start))
        logger.info("Step 4/5 DEPLOYED: %s", strategy_id)

        # 5. Start
        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.STARTING, "Deployment auto-start")
            await self.runtime.start(strategy_id)
            self.registry.update_state(strategy_id, StrategyLifecycleState.RUNNING, "Started successfully")
        except Exception as e:
            self.registry.update_state(strategy_id, StrategyLifecycleState.FAILED, f"Start failed: {e}")
            return DeployResult(success=False, strategy_id=strategy_id,
                                error=f"Start failed: {e}",
                                deploy_time_ms=self._elapsed_ms(t_start))
        logger.info("Step 5/5 RUNNING: %s", strategy_id)

        # Persist runtime state via snapshot
        await self._save_initial_snapshot(strategy_id)

        deploy_time = self._elapsed_ms(t_start)
        self._deployment_log.append({
            "strategy_id": strategy_id, "version": package.manifest.version,
            "success": True, "deploy_time_ms": deploy_time,
            "at": datetime.now(timezone.utc).isoformat(),
        })

        return DeployResult(
            success=True, strategy_id=strategy_id,
            version=package.manifest.version,
            state=StrategyLifecycleState.RUNNING,
            validation=validation,
            deploy_time_ms=deploy_time,
        )

    # ── Lifecycle Operations ──

    async def start(self, strategy_id: str) -> OperationResult:
        """Start a deployed strategy."""
        logger.info("Starting strategy: %s", strategy_id)
        metadata = self._require_metadata(strategy_id)
        prev = metadata.state

        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.STARTING, "Manual start")
            await self.runtime.start(strategy_id)
            self.registry.update_state(strategy_id, StrategyLifecycleState.RUNNING, "Started")
            return OperationResult(success=True, strategy_id=strategy_id,
                                   action="start", previous_state=prev,
                                   new_state=StrategyLifecycleState.RUNNING)
        except Exception as e:
            self.registry.update_state(strategy_id, StrategyLifecycleState.FAILED, str(e))
            return OperationResult(success=False, strategy_id=strategy_id,
                                   action="start", previous_state=prev,
                                   new_state=StrategyLifecycleState.FAILED, message=str(e))

    async def stop(self, strategy_id: str) -> OperationResult:
        """Gracefully stop a running strategy."""
        logger.info("Stopping strategy: %s", strategy_id)
        metadata = self._require_metadata(strategy_id)
        prev = metadata.state

        try:
            # Save snapshot before stopping
            await self.snapshot(strategy_id)

            self.registry.update_state(strategy_id, StrategyLifecycleState.STOPPING, "Manual stop")
            await self.runtime.stop(strategy_id)
            self.registry.update_state(strategy_id, StrategyLifecycleState.STOPPED, "Stopped")
            return OperationResult(success=True, strategy_id=strategy_id,
                                   action="stop", previous_state=prev,
                                   new_state=StrategyLifecycleState.STOPPED)
        except Exception as e:
            self.registry.update_state(strategy_id, StrategyLifecycleState.FAILED, str(e))
            return OperationResult(success=False, strategy_id=strategy_id,
                                   action="stop", previous_state=prev,
                                   new_state=StrategyLifecycleState.FAILED, message=str(e))

    async def pause(self, strategy_id: str) -> OperationResult:
        """Pause a running strategy."""
        logger.info("Pausing strategy: %s", strategy_id)
        metadata = self._require_metadata(strategy_id)
        prev = metadata.state

        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.PAUSING, "Manual pause")
            await self.runtime.pause(strategy_id)
            self.registry.update_state(strategy_id, StrategyLifecycleState.PAUSED, "Paused")
            return OperationResult(success=True, strategy_id=strategy_id,
                                   action="pause", previous_state=prev,
                                   new_state=StrategyLifecycleState.PAUSED)
        except Exception as e:
            return OperationResult(success=False, strategy_id=strategy_id,
                                   action="pause", previous_state=prev, message=str(e))

    async def resume(self, strategy_id: str) -> OperationResult:
        """Resume a paused strategy."""
        logger.info("Resuming strategy: %s", strategy_id)
        metadata = self._require_metadata(strategy_id)
        prev = metadata.state

        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.RESUMING, "Manual resume")
            await self.runtime.resume(strategy_id)
            self.registry.update_state(strategy_id, StrategyLifecycleState.RUNNING, "Resumed")
            return OperationResult(success=True, strategy_id=strategy_id,
                                   action="resume", previous_state=prev,
                                   new_state=StrategyLifecycleState.RUNNING)
        except Exception as e:
            return OperationResult(success=False, strategy_id=strategy_id,
                                   action="resume", previous_state=prev, message=str(e))

    async def restart(self, strategy_id: str) -> OperationResult:
        """Restart a strategy (stop → snapshot → start)."""
        logger.info("Restarting strategy: %s", strategy_id)
        stop_result = await self.stop(strategy_id)
        if not stop_result.success:
            return stop_result
        return await self.start(strategy_id)

    # ── Snapshot & Recovery ──

    async def snapshot(self, strategy_id: str) -> OperationResult:
        """Take a snapshot of a strategy's runtime state."""
        logger.info("Snapshot requested: %s", strategy_id)
        try:
            snapshot = await self.snapshot_manager.take_snapshot(
                strategy_id=strategy_id,
                runtime=self.runtime,
                registry=self.registry,
            )
            return OperationResult(
                success=True, strategy_id=strategy_id,
                action="snapshot",
                message=f"Snapshot {snapshot.snapshot_id} saved",
            )
        except Exception as e:
            return OperationResult(
                success=False, strategy_id=strategy_id,
                action="snapshot", message=str(e),
            )

    async def recover(self, strategy_id: str, snapshot_id: Optional[str] = None) -> OperationResult:
        """Recover a strategy from a snapshot."""
        logger.info("Recovery requested: %s (snapshot=%s)", strategy_id, snapshot_id or "latest")
        metadata = self._require_metadata(strategy_id)
        prev = metadata.state

        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.RECOVERING, "Recovery initiated")
            await self.recovery.recover(
                strategy_id=strategy_id,
                snapshot_id=snapshot_id,
                runtime=self.runtime,
                snapshot_manager=self.snapshot_manager,
                registry=self.registry,
            )
            self.registry.update_state(strategy_id, StrategyLifecycleState.RUNNING, "Recovery complete")
            return OperationResult(success=True, strategy_id=strategy_id,
                                   action="recover", previous_state=prev,
                                   new_state=StrategyLifecycleState.RUNNING,
                                   message="Recovery successful")
        except Exception as e:
            self.registry.update_state(strategy_id, StrategyLifecycleState.FAILED, f"Recovery failed: {e}")
            return OperationResult(success=False, strategy_id=strategy_id,
                                   action="recover", previous_state=prev,
                                   new_state=StrategyLifecycleState.FAILED, message=str(e))

    async def rollback(self, strategy_id: str, target_version: str) -> DeployResult:
        """Roll back a strategy to a previous version."""
        logger.info("Rollback requested: %s → %s", strategy_id, target_version)
        manifest = await self.repository.get_manifest(
            name=self.registry.get_manifest(strategy_id).name if self.registry.get_manifest(strategy_id) else "",
            version=target_version,
        )
        if manifest is None:
            return DeployResult(success=False, strategy_id=strategy_id,
                                error=f"Version {target_version} not found in repository")

        await self.stop(strategy_id)

        try:
            self.registry.update_state(strategy_id, StrategyLifecycleState.DEPLOYING, f"Rollback to {target_version}")
            self.registry.register(strategy_id, manifest)
            self.registry.update_state(strategy_id, StrategyLifecycleState.RUNNING, f"Rolled back to {target_version}")
            return DeployResult(
                success=True, strategy_id=strategy_id,
                version=target_version,
                state=StrategyLifecycleState.RUNNING,
            )
        except Exception as e:
            return DeployResult(success=False, strategy_id=strategy_id,
                                error=str(e))

    # ── Query ──

    async def status(self, strategy_id: str) -> Dict[str, Any]:
        """Get the current status of a strategy."""
        metadata = self.registry.get_metadata(strategy_id)
        manifest = self.registry.get_manifest(strategy_id)
        runtime_status = self.runtime.get_status(strategy_id)
        version_history = self.registry.get_version_history(strategy_id)

        return {
            "strategy_id": strategy_id,
            "state": metadata.state.value if metadata else "unknown",
            "version": manifest.version if manifest else "",
            "name": manifest.name if manifest else "",
            "runtime": runtime_status,
            "versions": version_history.to_dict() if version_history else {},
            "snapshots": self.snapshot_manager.list_snapshots(strategy_id),
        }

    async def list_strategies(
        self,
        state: Optional[StrategyLifecycleState] = None,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List strategies with optional filtering."""
        if active_only:
            ids = self.registry.list_active()
        elif state:
            ids = self.registry.list_by_state(state)
        else:
            ids = self.registry.list_all()

        results = []
        for sid in ids:
            status = await self.status(sid)
            results.append(status)
        return results

    async def list_versions(self, strategy_id: str) -> Dict[str, Any]:
        """List all versions for a strategy."""
        history = self.registry.get_version_history(strategy_id)
        if history:
            return history.to_dict()
        return {"strategy_id": strategy_id, "versions": []}

    # ── Internals ──

    def _require_metadata(self, strategy_id: str):
        """Get metadata or raise."""
        meta = self.registry.get_metadata(strategy_id)
        if meta is None:
            raise KeyError(f"Strategy not found: {strategy_id}")
        return meta

    async def _save_initial_snapshot(self, strategy_id: str) -> None:
        """Save an initial snapshot after deployment."""
        try:
            await self.snapshot_manager.take_snapshot(
                strategy_id=strategy_id,
                runtime=self.runtime,
                registry=self.registry,
                label="initial",
            )
        except Exception as e:
            logger.warning("Failed to save initial snapshot for %s: %s", strategy_id, e)

    def _elapsed_ms(self, start: datetime) -> float:
        return (datetime.now(timezone.utc) - start).total_seconds() * 1000

    # ── Properties ──

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == EngineState.READY

    def get_summary(self) -> Dict[str, Any]:
        return {
            "engine_state": self._state.value,
            "registry": self.registry.get_summary(),
            "runtime": self.runtime.get_summary(),
            "loader": self.loader.get_summary(),
            "validator": self.validator.get_summary(),
            "snapshots": self.snapshot_manager.get_summary(),
            "deployments": len(self._deployment_log),
        }
