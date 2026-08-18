"""
ICYQuant Platform - Main Service Facade

Unified platform service providing a single entry point for all
orchestration, runtime, and control plane operations.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .module_registry import ModuleRegistry, ModuleState, ModuleType
from .dependency_graph import DependencyGraph
from .lifecycle import LifecycleManager, LifecycleState
from .event_router import EventRouter, Event, EventPriority
from .workflow_engine import WorkflowEngine, WorkflowStatus
from .runtime import RuntimeManager, RuntimeState
from .orchestrator import PlatformOrchestrator
from .control_plane import ControlPlane
from .bootstrap import PlatformBootstrap
from .workspace import WorkspaceManager, Workspace, WorkspaceStatus
from .plugin_manager import PluginManager, PluginType
from .scheduler import TaskScheduler, ScheduleType
from .sdk.strategy_sdk import StrategySDK, StrategyPlugin, SignalAction
from .sdk.data_sdk import DataSDK, DataProviderPlugin
from .sdk.broker_sdk import BrokerSDK, BrokerAdapterPlugin, OrderSide
from .sdk.ai_sdk import AISDK, AIModelPlugin


logger = logging.getLogger(__name__)


class PlatformService:
    """
    Unified Platform Service Facade.

    Central entry point for the Institutional Quant Operating System.
    Coordinates: module registry, runtime, orchestrator, control plane,
    workspaces, plugins, schedulers, and SDKs.
    """

    def __init__(self, config_dir: str = "configs/platform"):
        self._registry = ModuleRegistry()
        self._runtime = RuntimeManager()
        self._lifecycle = LifecycleManager()
        self._event_router = EventRouter()
        self._workflow_engine = WorkflowEngine()
        self._dependency_graph = DependencyGraph()

        self._orchestrator = PlatformOrchestrator(
            registry=self._registry,
            runtime=self._runtime,
            event_router=self._event_router,
            workflow_engine=self._workflow_engine,
        )
        self._control_plane = ControlPlane(
            registry=self._registry,
            runtime=self._runtime,
            event_router=self._event_router,
            orchestrator=self._orchestrator,
        )
        self._bootstrap = PlatformBootstrap(
            config_dir=config_dir,
            registry=self._registry,
            runtime=self._runtime,
            lifecycle=self._lifecycle,
        )
        self._workspace_manager = WorkspaceManager()
        self._plugin_manager = PluginManager()
        self._scheduler = TaskScheduler()

        self._strategy_sdk = StrategySDK()
        self._data_sdk = DataSDK()
        self._broker_sdk = BrokerSDK()
        self._ai_sdk = AISDK()

        self._initialized = False
        self._init_default_modules()

    def _init_default_modules(self):
        default_modules = [
            ("market_data", ModuleType.DATA, "Market Data Service", ["lakehouse"]),
            ("lakehouse", ModuleType.INFRASTRUCTURE, "Data Lakehouse", []),
            ("research", ModuleType.RESEARCH, "Research Service", ["market_data"]),
            ("ai", ModuleType.AI, "AI Engine", ["feature_store", "lakehouse"]),
            ("feature_store", ModuleType.DATA, "Feature Store", ["lakehouse"]),
            ("backtest", ModuleType.TRADING, "Backtest Engine", ["research", "market_data"]),
            ("risk", ModuleType.RISK, "Risk Engine", ["market_data"]),
            ("oms", ModuleType.TRADING, "Order Management", ["risk"]),
            ("ems", ModuleType.TRADING, "Execution Management", ["oms"]),
            ("portfolio", ModuleType.PORTFOLIO, "Portfolio Engine", ["risk"]),
            ("reporting", ModuleType.CORE, "Reporting Service", ["portfolio"]),
            ("security", ModuleType.SECURITY, "Security Platform", []),
            ("observability", ModuleType.OBSERVABILITY, "Observability", []),
            ("cloud", ModuleType.INFRASTRUCTURE, "Cloud Platform", []),
        ]

        for name, mtype, desc, deps in default_modules:
            try:
                self._registry.register(
                    name=name,
                    module_type=mtype,
                    description=desc,
                    dependencies=deps,
                )
                self._runtime.register_module(name)
                self._lifecycle.register_module(name)
            except ValueError:
                pass

        self._initialized = True

    def start(self) -> bool:
        """Start the platform."""
        order = self._registry.ordered_by_dependencies()
        startup_order = [m.name for m in order]
        self._runtime.run_startup_sequence(startup_order)
        self._event_router.publish(
            "platform.started",
            payload={"modules": len(startup_order)},
            source="platform",
        )
        logger.info("Platform started")
        return True

    def stop(self) -> bool:
        """Stop the platform."""
        self._runtime.run_shutdown_sequence()
        self._scheduler.stop()
        self._event_router.publish(
            "platform.stopped",
            source="platform",
        )
        logger.info("Platform stopped")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get complete platform status."""
        return {
            "platform": {
                "state": self._runtime.get_global_state().value,
                "initialized": self._initialized,
            },
            "registry": self._registry.get_status(),
            "runtime": self._runtime.get_status(),
            "lifecycle": self._lifecycle.get_status(),
            "workflows": self._workflow_engine.get_status(),
            "eventRouter": self._event_router.get_status(),
            "plugins": self._plugin_manager.get_status(),
            "workspaces": self._workspace_manager.get_status(),
            "scheduler": self._scheduler.get_status(),
            "orchestrator": self._orchestrator.get_status(),
        }

    def register_module(
        self,
        name: str,
        module_type: ModuleType,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        instance: Optional[Any] = None,
    ) -> bool:
        try:
            self._registry.register(
                name=name,
                module_type=module_type,
                description=description,
                dependencies=dependencies,
                instance=instance,
            )
            self._runtime.register_module(name, instance=instance)
            self._lifecycle.register_module(name)
            return True
        except ValueError:
            return False

    def start_module(self, name: str) -> bool:
        self._lifecycle.start(name)
        return self._runtime.startup_module(name)

    def stop_module(self, name: str) -> bool:
        self._lifecycle.stop(name)
        return self._runtime.shutdown_module(name)

    def restart_module(self, name: str) -> bool:
        self._lifecycle.transition(name, LifecycleState.STOPPING)
        self._lifecycle.transition(name, LifecycleState.STOPPED)
        self._lifecycle.transition(name, LifecycleState.INITIALIZING)
        self._lifecycle.transition(name, LifecycleState.RUNNING)
        return self._runtime.restart_module(name)

    def get_modules(self, module_type: Optional[ModuleType] = None) -> List[Dict]:
        if module_type:
            return [m.to_dict() for m in self._registry.get_by_type(module_type)]
        return [m.to_dict() for m in self._registry.get_all()]

    def get_module_names(self) -> List[str]:
        return self._registry.list_names()

    def create_workspace(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Workspace:
        return self._workspace_manager.create_workspace(name, config)

    def run_workflow(
        self,
        name: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        template: Optional[str] = None,
    ) -> str:
        wf = self._workflow_engine.create_workflow(name, steps, template)
        self._workflow_engine.start_workflow(wf.workflow_id)
        return wf.workflow_id

    def subscribe_event(
        self,
        subscriber_id: str,
        topic: str,
        handler: Any,
    ) -> str:
        return self._event_router.subscribe(subscriber_id, topic, handler)

    def publish_event(
        self,
        topic: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "",
    ):
        return self._event_router.publish(topic, payload, source)

    def load_plugin(
        self,
        name: str,
        plugin_type: PluginType,
        version: str = "1.0.0",
    ) -> bool:
        self._plugin_manager.register_plugin(name, plugin_type, version=version)
        self._plugin_manager.load_plugin(name)
        self._plugin_manager.initialize_plugin(name)
        return self._plugin_manager.start_plugin(name)

    def register_strategy(self, strategy: StrategyPlugin) -> str:
        return self._strategy_sdk.register(strategy)

    def register_broker(self, broker: BrokerAdapterPlugin) -> str:
        return self._broker_sdk.register(broker)

    def register_ai_model(self, model: AIModelPlugin) -> str:
        return self._ai_sdk.register(model)

    def register_data_provider(self, provider: DataProviderPlugin) -> str:
        return self._data_sdk.register(provider)

    def pause_trading(self, reason: str = "manual") -> Dict[str, Any]:
        return self._control_plane.pause_trading(reason)

    def resume_trading(self, reason: str = "manual") -> Dict[str, Any]:
        return self._control_plane.resume_trading(reason)

    def emergency_halt(self, reason: str = "critical") -> Dict[str, Any]:
        return self._orchestrator.orchestrate_emergency_halt(reason)

    def schedule_task(
        self,
        name: str,
        handler: Any,
        interval_seconds: int = 60,
    ) -> str:
        task = self._scheduler.add_task(
            name, handler,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
        )
        return task.task_id

    def to_dict(self) -> Dict:
        return self.get_status()
