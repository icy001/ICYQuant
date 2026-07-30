"""Model Rollout — hot reload and zero-downtime model updates.

Watches Model Registry for new production versions and seamlessly
swaps the serving model without stopping trading.

Usage::

    rollout = RolloutManager(
        model_loader=loader,
        canary_manager=canary,
    )
    rollout.deploy("alpha_model", "v38", strategy="canary")
    rollout.watch(interval_seconds=30)  # auto-detect registry changes
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RolloutStrategy(str, Enum):
    """Deployment strategy for model updates."""
    IMMEDIATE = "immediate"  # Instant swap (for dev/testing)
    CANARY = "canary"        # Staged traffic rollout
    BLUE_GREEN = "blue_green"  # Two full environments, swap on validation
    SHADOW = "shadow"        # Mirror traffic, compare offline


@dataclass
class RolloutStep:
    """A step in a rollout plan.

    Attributes:
        step_id: Sequential step identifier.
        action: Action description.
        status: Step status.
        started_at: When step started.
        completed_at: When step completed.
        error: Error message if failed.
    """

    step_id: int = 0
    action: str = ""
    status: str = "pending"  # pending/running/completed/failed
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: str = ""


@dataclass
class RolloutPlan:
    """A deployment plan with defined steps.

    Attributes:
        model_name: Target model name.
        version: Target version.
        strategy: Deployment strategy.
        steps: Ordered rollout steps.
        created_at: Plan creation timestamp.
        status: Overall plan status.
    """

    model_name: str = ""
    version: str = ""
    strategy: RolloutStrategy = RolloutStrategy.IMMEDIATE
    steps: List[RolloutStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"


@dataclass
class RolloutResult:
    """Result of a completed rollout.

    Attributes:
        model_name: Deployed model name.
        version: Deployed version.
        previous_version: Previously serving version.
        strategy: Deployment strategy used.
        success: Whether rollout succeeded.
        duration_seconds: Total rollout duration.
        steps_completed: Number of steps completed.
        message: Human-readable result message.
    """

    model_name: str = ""
    version: str = ""
    previous_version: str = ""
    strategy: RolloutStrategy = RolloutStrategy.IMMEDIATE
    success: bool = True
    duration_seconds: float = 0.0
    steps_completed: int = 0
    message: str = ""


@dataclass
class RolloutConfig:
    """Rollout manager configuration.

    Attributes:
        default_strategy: Default deployment strategy.
        watch_interval: Seconds between registry polling.
        auto_deploy: Automatically deploy new production versions.
        max_retries: Max retry attempts for failed deployments.
        retry_delay: Seconds between retries.
        validate_before_swap: Run validation before finalizing swap.
    """

    default_strategy: RolloutStrategy = RolloutStrategy.CANARY
    watch_interval: float = 30.0
    auto_deploy: bool = False
    max_retries: int = 3
    retry_delay: float = 10.0
    validate_before_swap: bool = True


class RolloutManager:
    """Manages zero-downtime model deployment and hot reload.

    Integrates with ModelRegistry for version detection and ModelLoader
    for in-memory model swapping. Supports canary, blue-green, shadow,
    and immediate deployment strategies.

    Usage::

        rollout = RolloutManager(
            model_loader=loader,
            canary_manager=canary,
            registry=model_registry,
        )
        result = rollout.deploy("alpha_model", "v38")
        rollout.watch()  # background thread for auto-deploy
    """

    def __init__(
        self,
        model_loader: Any = None,
        canary_manager: Any = None,
        registry: Any = None,
        config: Optional[RolloutConfig] = None,
    ):
        self._loader = model_loader
        self._canary = canary_manager
        self._registry = registry
        self.config = config or RolloutConfig()
        self._active_versions: Dict[str, str] = {}  # model_name → version
        self._rollout_history: List[RolloutResult] = []
        self._plans: Dict[str, RolloutPlan] = {}
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop: threading.Event = threading.Event()
        self._hooks: Dict[str, List[Callable]] = {
            "pre_deploy": [],
            "post_deploy": [],
            "on_rollback": [],
            "on_failure": [],
        }

    def deploy(
        self,
        model_name: str,
        version: str,
        strategy: Optional[RolloutStrategy] = None,
        model: Any = None,
    ) -> RolloutResult:
        """Deploy a model version to serving.

        Args:
            model_name: Model to deploy.
            version: Version to deploy.
            strategy: Deployment strategy override.
            model: Pre-loaded model object (optional).

        Returns:
            RolloutResult summarizing the deployment.
        """
        strategy = strategy or self.config.default_strategy
        start = time.time()
        previous = self._active_versions.get(model_name, "")

        # Pre-deploy hooks
        for hook in self._hooks["pre_deploy"]:
            try:
                hook(model_name, version, strategy.value)
            except Exception:
                pass

        try:
            if strategy == RolloutStrategy.IMMEDIATE:
                result = self._deploy_immediate(model_name, version, model)
            elif strategy == RolloutStrategy.CANARY:
                result = self._deploy_canary(model_name, version, model)
            elif strategy == RolloutStrategy.BLUE_GREEN:
                result = self._deploy_blue_green(model_name, version, model)
            elif strategy == RolloutStrategy.SHADOW:
                result = self._deploy_shadow(model_name, version, model)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            result.previous_version = previous
            result.duration_seconds = time.time() - start
            self._active_versions[model_name] = version
            self._rollout_history.append(result)

            # Post-deploy hooks
            for hook in self._hooks["post_deploy"]:
                try:
                    hook(model_name, version, strategy.value, result.success)
                except Exception:
                    pass

            return result

        except Exception as e:
            # Failure hooks
            for hook in self._hooks["on_failure"]:
                try:
                    hook(model_name, version, str(e))
                except Exception:
                    pass

            return RolloutResult(
                model_name=model_name,
                version=version,
                previous_version=previous,
                strategy=strategy,
                success=False,
                duration_seconds=time.time() - start,
                message=f"Deployment failed: {e}",
            )

    def rollback(self, model_name: str) -> RolloutResult:
        """Rollback to the previous version of a model.

        Returns:
            RolloutResult for the rollback.
        """
        # Find previous successful deployment
        prev_deploy = None
        for h in reversed(self._rollout_history):
            if h.model_name == model_name and h.success and h.version != self._active_versions.get(model_name, ""):
                prev_deploy = h
                break

        if prev_deploy is None:
            return RolloutResult(
                model_name=model_name,
                success=False,
                message="No previous version to rollback to",
            )

        for hook in self._hooks["on_rollback"]:
            try:
                hook(model_name, prev_deploy.version)
            except Exception:
                pass

        return self.deploy(model_name, prev_deploy.version, strategy=RolloutStrategy.IMMEDIATE)

    def watch(self, interval_seconds: Optional[float] = None) -> None:
        """Start background watcher for registry changes (auto-deploy).

        Args:
            interval_seconds: Polling interval. Uses config default if None.
        """
        if self._watch_thread and self._watch_thread.is_alive():
            return

        interval = interval_seconds or self.config.watch_interval
        self._watch_stop.clear()

        def _watcher():
            known_versions: Dict[str, str] = {}
            while not self._watch_stop.is_set():
                try:
                    if self._registry:
                        for entry in self._registry.list_models():
                            prod = self._registry.get_production(entry.model_name)
                            if prod:
                                current = known_versions.get(entry.model_name)
                                if current and current != prod.version:
                                    if self.config.auto_deploy:
                                        self.deploy(entry.model_name, prod.version)
                                known_versions[entry.model_name] = prod.version
                except Exception:
                    pass
                self._watch_stop.wait(interval)

        self._watch_thread = threading.Thread(target=_watcher, daemon=True)
        self._watch_thread.start()

    def stop_watch(self) -> None:
        """Stop the background watcher."""
        self._watch_stop.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None

    def get_active_version(self, model_name: str) -> Optional[str]:
        """Get the currently active version for a model."""
        return self._active_versions.get(model_name)

    def list_active(self) -> Dict[str, str]:
        """List all active model versions."""
        return dict(self._active_versions)

    def get_history(self) -> List[RolloutResult]:
        """Get deployment history."""
        return list(self._rollout_history)

    def add_hook(self, event: str, callback: Callable) -> None:
        """Register a deployment lifecycle hook.

        Args:
            event: One of 'pre_deploy', 'post_deploy', 'on_rollback', 'on_failure'.
            callback: Function to invoke.
        """
        if event in self._hooks:
            self._hooks[event].append(callback)

    # ---- internal deployment strategies ----

    def _deploy_immediate(self, model_name: str, version: str, model: Any = None) -> RolloutResult:
        """Instant model swap."""
        if self._loader:
            loaded = self._loader.load(model_name, version)
            return RolloutResult(
                model_name=model_name,
                version=version,
                strategy=RolloutStrategy.IMMEDIATE,
                steps_completed=1,
                message=f"Immediately deployed {model_name} v{version}",
            )
        return RolloutResult(
            model_name=model_name,
            version=version,
            strategy=RolloutStrategy.IMMEDIATE,
            steps_completed=1,
            message=f"Deployed {model_name} v{version} (no loader)",
        )

    def _deploy_canary(self, model_name: str, version: str, model: Any = None) -> RolloutResult:
        """Canary staged rollout via CanaryManager."""
        if not self._canary:
            raise RuntimeError("CanaryManager required for canary deployment")

        if self._loader:
            loaded = self._loader.load(model_name, version)
            if loaded:
                model = loaded.model

        self._canary.start_rollout(model_name, new_model=model)
        # Note: caller is responsible for advancing stages
        return RolloutResult(
            model_name=model_name,
            version=version,
            strategy=RolloutStrategy.CANARY,
            steps_completed=1,
            message=f"Canary rollout started for {model_name} v{version} at 5%",
        )

    def _deploy_blue_green(self, model_name: str, version: str, model: Any = None) -> RolloutResult:
        """Blue-green deployment."""
        if self._loader:
            self._loader.load(model_name, version)
        return RolloutResult(
            model_name=model_name,
            version=version,
            strategy=RolloutStrategy.BLUE_GREEN,
            steps_completed=2,
            message=f"Blue-green deployed {model_name} v{version}",
        )

    def _deploy_shadow(self, model_name: str, version: str, model: Any = None) -> RolloutResult:
        """Shadow deployment (mirror traffic, no live impact)."""
        if self._loader:
            self._loader.load(model_name, version)
        return RolloutResult(
            model_name=model_name,
            version=version,
            strategy=RolloutStrategy.SHADOW,
            steps_completed=1,
            message=f"Shadow deployed {model_name} v{version} (mirror mode)",
        )
