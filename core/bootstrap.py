"""
ICYQuant Application Bootstrap.

Production-grade application bootstrap manager.

Responsibilities:

- Application initialization
- Startup orchestration
- Component lifecycle
- Dependency initialization
- Graceful shutdown
- Rollback recovery
- Health monitoring
- State management
- Runtime statistics

Python:
    3.12+
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from traceback import format_exc
from typing import Any

from core.container import (
    Container,
    get_container,
)
from core.logging import (
    initialize_logging,
    get_or_create_logger,
    LoggerType,
)
from core.settings import (
    Settings,
    get_settings,
)


# ============================================================================
# Type Aliases
# ============================================================================


LifecycleCallback = Callable[[], Awaitable[None]]

HealthChecker = Callable[[], Awaitable[tuple[bool, str]]]


# ============================================================================
# Application State
# ============================================================================


class ApplicationState(str, Enum):
    """
    Global application lifecycle state.

    Defines the possible states an application
    can be in during its lifecycle.
    """

    CREATED = "created"

    STARTING = "starting"

    RUNNING = "running"

    STOPPING = "stopping"

    STOPPED = "stopped"

    FAILED = "failed"


# ============================================================================
# State Transition Validation
# ============================================================================


_ALLOWED_STATE_TRANSITIONS: dict[
    ApplicationState, set[ApplicationState]
] = {
    ApplicationState.CREATED: {
        ApplicationState.STARTING,
    },
    ApplicationState.STARTING: {
        ApplicationState.RUNNING,
        ApplicationState.FAILED,
    },
    ApplicationState.RUNNING: {
        ApplicationState.STOPPING,
    },
    ApplicationState.STOPPING: {
        ApplicationState.STOPPED,
    },
    ApplicationState.FAILED: {
        ApplicationState.STOPPING,
    },
    ApplicationState.STOPPED: set(),
}


class InvalidStateTransitionError(RuntimeError):
    """
    Invalid application state transition.

    Raised when attempting an invalid state
    transition according to the state machine.
    """

    pass


# ============================================================================
# Startup Stage
# ============================================================================


class StartupStage(str, Enum):
    """
    Application startup stages.

    Stages are executed in order. Each stage
    represents a discrete initialization phase
    that can be independently monitored and
    rolled back on failure.
    """

    SETTINGS = "settings"

    LOGGING = "logging"

    CONTAINER = "container"

    DATABASE = "database"

    CACHE = "cache"

    MESSAGE_BUS = "message_bus"

    BROKER = "broker"

    SERVICES = "services"

    API = "api"

    READY = "ready"


# ============================================================================
# Stage Result
# ============================================================================


@dataclass
class StageResult:
    """
    Startup stage execution result.

    Captures timing, success status, and
    error information for each stage.
    """

    stage: StartupStage

    success: bool

    elapsed_ms: float

    error: str | None = None


# ============================================================================
# Lifecycle Hooks
# ============================================================================


@dataclass
class LifecycleHooks:
    """
    Application lifecycle hooks.

    Allows external code to register callbacks
    that execute at specific lifecycle points.
    """

    before_startup: list[
        LifecycleCallback
    ] = field(default_factory=list)

    after_startup: list[
        LifecycleCallback
    ] = field(default_factory=list)

    before_shutdown: list[
        LifecycleCallback
    ] = field(default_factory=list)

    after_shutdown: list[
        LifecycleCallback
    ] = field(default_factory=list)


# ============================================================================
# Health Registry
# ============================================================================


@dataclass
class HealthStatus:
    """
    Health status for a single component.
    """

    component: str

    healthy: bool

    message: str = "OK"


class HealthRegistry:
    """
    Runtime health registry.

    Tracks health status of registered components
    and provides overall health status.
    """

    def __init__(self) -> None:

        self._components: dict[
            str, HealthStatus
        ] = {}

    def register(
        self,
        component: str,
    ) -> None:
        """
        Register a component.

        Initially marked as healthy.
        """

        self._components[component] = (
            HealthStatus(
                component=component,
                healthy=True,
            )
        )

    def update(
        self,
        component: str,
        healthy: bool,
        message: str = "OK",
    ) -> None:
        """
        Update component health status.
        """

        self._components[component] = (
            HealthStatus(
                component=component,
                healthy=healthy,
                message=message,
            )
        )

    def get(
        self,
        component: str,
    ) -> HealthStatus | None:
        """
        Get component health status.
        """

        return self._components.get(component)

    def overall_status(
        self,
    ) -> bool:
        """
        Return overall health status.

        True if all components are healthy.
        """

        if not self._components:
            return True

        return all(
            status.healthy
            for status in self._components.values()
        )

    def snapshot(
        self,
    ) -> list[HealthStatus]:
        """
        Return snapshot of all component statuses.
        """

        return list(
            self._components.values()
        )


# ============================================================================
# Bootstrap Context
# ============================================================================


@dataclass
class BootstrapContext:
    """
    Bootstrap runtime state.

    Tracks the current application state
    during initialization and shutdown.
    """

    settings: Settings

    container: Container

    state: ApplicationState = (
        ApplicationState.CREATED
    )

    health: HealthRegistry = field(
        default_factory=HealthRegistry
    )

    started_stages: list[
        StartupStage
    ] = field(default_factory=list)

    results: list[
        StageResult
    ] = field(default_factory=list)

    hooks: LifecycleHooks = field(
        default_factory=LifecycleHooks
    )

    startup_time_ms: float = 0.0

    total_startup_ms: float = 0.0

    successful: bool = False


# ============================================================================
# Bootstrap Manager
# ============================================================================


class BootstrapManager:
    """
    Application bootstrap manager.

    Orchestrates the full application lifecycle
    including startup, readiness checks, and
    graceful shutdown with rollback recovery.
    """

    def __init__(self) -> None:

        self._settings: Settings | None = None

        self._container: Container | None = None

        self._context: BootstrapContext | None = None

        self._logger_type = (
            LoggerType.APPLICATION
        )

        self._logger = None

        self._health_checkers: dict[
            str, HealthChecker
        ] = {}

    @property
    def context(
        self,
    ) -> BootstrapContext:
        """
        Return bootstrap context.
        """

        if self._context is None:
            raise RuntimeError(
                "Bootstrap not initialized. "
                "Call startup() first."
            )

        return self._context

    @property
    def state(
        self,
    ) -> ApplicationState:
        """
        Return current application state.
        """

        return self.context.state

    def _get_logger(self):
        """
        Get or create application logger.

        Must be called after initialize_logging().
        """

        if self._logger is None:
            self._logger = (
                get_or_create_logger(
                    self._logger_type
                )
            )

        return self._logger

    def set_state(
        self,
        state: ApplicationState,
    ) -> None:
        """
        Set application state.

        Validates transition and logs state changes
        for observability.
        """

        current = self._context.state

        allowed = _ALLOWED_STATE_TRANSITIONS[
            current
        ]

        if state not in allowed:
            raise InvalidStateTransitionError(
                f"{current.value} -> {state.value} "
                "is not allowed."
            )

        self._context.state = state

        self._get_logger().info(
            "application_state",
            state=state.value,
        )

    def mark_stage(
        self,
        stage: StartupStage,
    ) -> None:
        """
        Mark startup stage complete.

        Records the stage in the context and
        logs a structured event for observability.
        """

        self._context.started_stages.append(
            stage
        )

        self._get_logger().info(
            "startup_stage_completed",
            stage=stage.value,
        )

    # --------------------------------------------------------
    # Hook Registration
    # --------------------------------------------------------

    def add_before_startup(
        self,
        callback: LifecycleCallback,
    ) -> None:
        """
        Register before-startup hook.
        """

        if self._context is None:
            raise RuntimeError(
                "Bootstrap not initialized."
            )

        self._context.hooks.before_startup.append(
            callback
        )

    def add_after_startup(
        self,
        callback: LifecycleCallback,
    ) -> None:
        """
        Register after-startup hook.
        """

        if self._context is None:
            raise RuntimeError(
                "Bootstrap not initialized."
            )

        self._context.hooks.after_startup.append(
            callback
        )

    def add_before_shutdown(
        self,
        callback: LifecycleCallback,
    ) -> None:
        """
        Register before-shutdown hook.
        """

        if self._context is None:
            raise RuntimeError(
                "Bootstrap not initialized."
            )

        self._context.hooks.before_shutdown.append(
            callback
        )

    def add_after_shutdown(
        self,
        callback: LifecycleCallback,
    ) -> None:
        """
        Register after-shutdown hook.
        """

        if self._context is None:
            raise RuntimeError(
                "Bootstrap not initialized."
            )

        self._context.hooks.after_shutdown.append(
            callback
        )

    # --------------------------------------------------------
    # Hook Executor
    # --------------------------------------------------------

    async def _execute_hooks(
        self,
        callbacks: list[LifecycleCallback],
    ) -> None:
        """
        Execute lifecycle hooks.

        Hooks are executed in order. Errors are
        logged but do not interrupt execution.
        """

        for callback in callbacks:
            try:
                await callback()
            except Exception:
                self._get_logger().exception(
                    "lifecycle_hook_failed",
                    hook=callback.__name__,
                )

    # --------------------------------------------------------
    # Stage Executor
    # --------------------------------------------------------

    async def execute_stage(
        self,
        stage: StartupStage,
        callback: LifecycleCallback,
    ) -> None:
        """
        Execute startup stage.

        Wraps stage execution with timing,
        error handling, and logging.
        """

        start = perf_counter()

        try:

            await callback()

            elapsed = (
                perf_counter() - start
            ) * 1000

            self._context.results.append(

                StageResult(

                    stage=stage,

                    success=True,

                    elapsed_ms=elapsed,
                )
            )

            self.mark_stage(stage)

            self._get_logger().info(

                "startup_stage",

                stage=stage.value,

                elapsed_ms=round(elapsed, 2),
            )

        except Exception:

            elapsed = (
                perf_counter() - start
            ) * 1000

            self._context.results.append(

                StageResult(

                    stage=stage,

                    success=False,

                    elapsed_ms=elapsed,

                    error=format_exc(),
                )
            )

            self._get_logger().exception(

                "startup_failed",

                stage=stage.value,
            )

            raise

    # --------------------------------------------------------
    # Rollback
    # --------------------------------------------------------

    async def rollback(
        self,
    ) -> None:
        """
        Rollback started stages.

        Called when startup fails to release
        any resources that were already initialized.
        """

        self._get_logger().warning(

            "startup_rollback",

            stages=len(
                self._context.started_stages
            ),
        )

        try:

            await self._container.shutdown()

        except Exception:

            self._get_logger().exception(
                "rollback_failed"
            )

        finally:

            self._context.started_stages.clear()

    # --------------------------------------------------------
    # Readiness / Liveness
    # --------------------------------------------------------

    def is_ready(
        self,
    ) -> bool:
        """
        Whether application is ready.

        Ready means RUNNING state and all
        health checks passing.
        """

        if self._context is None:
            return False

        return (
            self._context.state
            == ApplicationState.RUNNING
            and
            self._context.health.overall_status()
        )

    def is_alive(
        self,
    ) -> bool:
        """
        Process liveness.

        Alive means not STOPPED.
        """

        if self._context is None:
            return False

        return (
            self._context.state
            != ApplicationState.STOPPED
        )

    # --------------------------------------------------------
    # Health Check
    # --------------------------------------------------------

    def register_health_checker(
        self,
        component: str,
        checker: HealthChecker,
    ) -> None:
        """
        Register async health checker.

        Health checkers are called periodically
        to update component health status.
        """

        self._health_checkers[component] = checker

    async def check_health(
        self,
    ) -> None:
        """
        Execute all health checkers.

        Updates health registry with results.
        """

        for component, checker in (
            self._health_checkers.items()
        ):
            try:
                healthy, message = (
                    await checker()
                )

                self._context.health.update(
                    component,
                    healthy,
                    message,
                )
            except Exception:
                self._get_logger().exception(
                    "health_check_failed",
                    component=component,
                )

                self._context.health.update(
                    component,
                    False,
                    "Health check error",
                )

    async def monitor_health(
        self,
        interval: int = 30,
    ) -> None:
        """
        Background health monitor.

        Periodically executes health checkers
        while application is alive.
        """

        while self.is_alive():
            await self.check_health()
            await asyncio.sleep(interval)

    # --------------------------------------------------------
    # Startup Pipeline
    # --------------------------------------------------------

    async def startup(
        self,
    ) -> BootstrapContext:
        """
        Complete application startup.

        Executes all startup stages in order
        with proper error handling and metrics.
        Rolls back on failure.
        """

        total = perf_counter()

        # Initialize logging first
        initialize_logging()

        # Create logger after logging is initialized
        self._get_logger()

        # Initialize context
        self._settings = get_settings()
        self._container = get_container()

        self._context = BootstrapContext(
            settings=self._settings,
            container=self._container,
        )

        # Transition to STARTING
        self.set_state(ApplicationState.STARTING)

        # Register health components
        self._context.health.register("settings")
        self._context.health.register("container")
        self._context.health.register("database")
        self._context.health.register("redis")
        self._context.health.register("kafka")
        self._context.health.register("broker")

        # Execute before-startup hooks
        await self._execute_hooks(
            self._context.hooks.before_startup
        )

        try:

            # Mark logging stage complete
            self.mark_stage(StartupStage.LOGGING)

            # Execute startup pipeline
            await self.execute_stage(
                StartupStage.SETTINGS,
                self._startup_settings,
            )

            await self.execute_stage(
                StartupStage.CONTAINER,
                self._startup_container,
            )

            await self.execute_stage(
                StartupStage.DATABASE,
                self._startup_database,
            )

            await self.execute_stage(
                StartupStage.CACHE,
                self._startup_cache,
            )

            await self.execute_stage(
                StartupStage.MESSAGE_BUS,
                self._startup_message_bus,
            )

            await self.execute_stage(
                StartupStage.BROKER,
                self._startup_broker,
            )

            await self.execute_stage(
                StartupStage.SERVICES,
                self._startup_services,
            )

            await self.execute_stage(
                StartupStage.API,
                self._startup_api,
            )

            # Mark ready
            self.mark_stage(StartupStage.READY)

            # Calculate total startup time
            self._context.total_startup_ms = (
                perf_counter() - total
            ) * 1000

            self._context.successful = True

            # Transition to RUNNING
            self.set_state(ApplicationState.RUNNING)

            # Execute after-startup hooks
            await self._execute_hooks(
                self._context.hooks.after_startup
            )

            self._get_logger().info(
                "startup_complete",
                total_startup_ms=round(
                    self._context.total_startup_ms, 2
                ),
                stages=len(
                    self._context.started_stages
                ),
            )

            return self._context

        except Exception:

            # Transition to FAILED
            self.set_state(ApplicationState.FAILED)

            # Rollback on failure
            await self.rollback()

            raise

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    async def shutdown(
        self,
    ) -> None:
        """
        Gracefully shutdown application.

        Executes shutdown hooks and releases
        all container resources.
        """

        if self._context is None:
            return

        # Transition to STOPPING
        self.set_state(ApplicationState.STOPPING)

        # Execute before-shutdown hooks
        await self._execute_hooks(
            self._context.hooks.before_shutdown
        )

        # Shutdown container
        try:
            await self._container.shutdown()
        except Exception:
            self._get_logger().exception(
                "container_shutdown_failed"
            )

        # Execute after-shutdown hooks
        await self._execute_hooks(
            self._context.hooks.after_shutdown
        )

        self._get_logger().info(
            "application_shutdown"
        )

        # Transition to STOPPED
        self.set_state(ApplicationState.STOPPED)

        # Reset state
        self._context.successful = False
        self._context.started_stages.clear()

    # --------------------------------------------------------
    # Startup Hooks (Override in subclasses)
    # --------------------------------------------------------

    async def _startup_settings(
        self,
    ) -> None:
        """
        Initialize settings stage.

        Settings are already loaded during
        BootstrapManager initialization.
        """

        pass

    async def _startup_container(
        self,
    ) -> None:
        """
        Initialize container stage.

        Pre-create singleton instances.
        """

        await self._container.startup_async()

    async def _startup_database(
        self,
    ) -> None:
        """
        Initialize database connections.

        Override to connect PostgreSQL, etc.
        """

        pass

    async def _startup_cache(
        self,
    ) -> None:
        """
        Initialize cache layer.

        Override to connect Redis, etc.
        """

        pass

    async def _startup_message_bus(
        self,
    ) -> None:
        """
        Initialize message bus.

        Override to connect Kafka, etc.
        """

        pass

    async def _startup_broker(
        self,
    ) -> None:
        """
        Initialize broker connections.

        Override to connect trading brokers.
        """

        pass

    async def _startup_services(
        self,
    ) -> None:
        """
        Initialize business services.

        Override to register and start
        domain services.
        """

        pass

    async def _startup_api(
        self,
    ) -> None:
        """
        Initialize API layer.

        Override to start FastAPI, etc.
        """

        pass

    # --------------------------------------------------------
    # Bootstrap Report
    # --------------------------------------------------------

    def report(
        self,
    ) -> dict[str, Any]:
        """
        Bootstrap summary report.

        Returns complete startup status including
        stages, health, and timing information.
        """

        return {
            "state": self.state.value,
            "startup_ms": round(
                self._context.total_startup_ms, 2
            ),
            "ready": self.is_ready(),
            "alive": self.is_alive(),
            "stages": [
                {
                    "stage": item.stage.value,
                    "success": item.success,
                    "elapsed_ms": round(
                        item.elapsed_ms, 2
                    ),
                }
                for item in self._context.results
            ],
            "health": [
                {
                    "component": x.component,
                    "healthy": x.healthy,
                    "message": x.message,
                }
                for x in self._context.health.snapshot()
            ],
        }

    # --------------------------------------------------------
    # Runtime Statistics
    # --------------------------------------------------------

    def runtime_statistics(
        self,
    ) -> dict[str, Any]:
        """
        Runtime statistics.

        Returns summary statistics for monitoring
        and observability systems.
        """

        return {
            "state": self.state.value,
            "components": len(
                self._context.health.snapshot()
            ),
            "startup_time_ms": round(
                self._context.total_startup_ms, 2
            ),
            "healthy": (
                self._context.health.overall_status()
            ),
        }

    # --------------------------------------------------------
    # Legacy Compatibility
    # --------------------------------------------------------

    async def initialize(
        self,
    ) -> BootstrapContext:
        """
        Initialize bootstrap process (legacy).

        Deprecated: Use startup() instead.
        """

        return await self.startup()


# ============================================================================
# Default Bootstrap
# ============================================================================

_bootstrap = BootstrapManager()


def get_bootstrap() -> BootstrapManager:
    """
    Return global bootstrap manager.

    Provides a global singleton for application
    lifecycle management across the entire
    codebase.
    """

    return _bootstrap