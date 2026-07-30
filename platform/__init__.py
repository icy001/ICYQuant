"""
ICYQuant Platform - Institutional Quant Operating System

Final integration platform that orchestrates all ICYQuant modules:
Trading, Risk, AI, Portfolio, Research, Market Data, etc.
"""

import sys
import os
import importlib
import importlib.util

# ---------------------------------------------------------------------------
# Fix the shadowing of Python's stdlib 'platform' module.
# Our package is named 'platform', which shadows the stdlib 'platform'.
# This causes third-party libraries (numpy, httpx, zstandard, etc.) to fail
# when they try to import platform.python_implementation() or other stdlib
# platform functions.
#
# Strategy: after loading all our submodules, we populate our package with
# all attributes from the real stdlib 'platform' module. This way:
# - 'import platform' returns our package (correct for our code)
# - platform.python_implementation() and other stdlib calls work correctly
# - Our package remains the single entry point for everything
# ---------------------------------------------------------------------------

from .module_registry import (
    ModuleRegistry,
    ModuleInfo,
    ModuleState,
    ModuleType,
)
from .dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyType,
)
from .lifecycle import (
    LifecycleManager,
    LifecyclePhase,
    LifecycleState,
)
from .event_router import (
    EventRouter,
    Event,
    EventPriority,
    EventSubscription,
)
from .workflow_engine import (
    WorkflowEngine,
    Workflow,
    WorkflowStep,
    WorkflowStatus,
)
from .runtime import (
    RuntimeManager,
    RuntimeState,
    ModuleRuntime,
)
from .orchestrator import PlatformOrchestrator
from .control_plane import ControlPlane
from .bootstrap import PlatformBootstrap
from .workspace import WorkspaceManager, Workspace
from .plugin_manager import PluginManager, PluginInfo
from .scheduler import TaskScheduler, ScheduledTask
from .sdk.strategy_sdk import StrategySDK, StrategyPlugin
from .sdk.data_sdk import DataSDK, DataProviderPlugin
from .sdk.broker_sdk import BrokerSDK, BrokerAdapterPlugin
from .sdk.ai_sdk import AISDK, AIModelPlugin
from .sdk import PluginBase, PluginMetadata

# Re-export all stdlib 'platform' module attributes so that third-party
# packages calling platform.python_implementation() etc. work correctly.
def _reexport_stdlib_platform():
    """Copy all attributes from stdlib platform module to our package."""
    try:
        import sysconfig
        stdlib_dir = sysconfig.get_path("stdlib")
    except Exception:
        stdlib_dir = os.path.dirname(os.__file__)

    real_platform_file = os.path.join(stdlib_dir, "platform.py")
    if not os.path.exists(real_platform_file):
        python_root = os.path.dirname(os.path.dirname(os.__file__))
        real_platform_file = os.path.join(python_root, "Lib", "platform.py")

    if os.path.exists(real_platform_file):
        # Load the real stdlib module without caching it as 'platform'
        spec = importlib.util.spec_from_file_location(
            "_stdlib_platform", real_platform_file
        )
        real_platform = importlib.util.module_from_spec(spec)
        sys.modules["_stdlib_platform"] = real_platform
        spec.loader.exec_module(real_platform)

        # Copy all public attributes to our package
        for attr in dir(real_platform):
            if not attr.startswith("_"):
                globals()[attr] = getattr(real_platform, attr)

        # Clean up temporary module
        del sys.modules["_stdlib_platform"]

_reexport_stdlib_platform()

__all__ = [
    "ModuleRegistry",
    "ModuleInfo",
    "ModuleState",
    "ModuleType",
    "DependencyGraph",
    "DependencyNode",
    "DependencyType",
    "LifecycleManager",
    "LifecyclePhase",
    "LifecycleState",
    "EventRouter",
    "Event",
    "EventPriority",
    "EventSubscription",
    "WorkflowEngine",
    "Workflow",
    "WorkflowStep",
    "WorkflowStatus",
    "RuntimeManager",
    "RuntimeState",
    "ModuleRuntime",
    "PlatformOrchestrator",
    "ControlPlane",
    "PlatformBootstrap",
    "WorkspaceManager",
    "Workspace",
    "PluginManager",
    "PluginInfo",
    "TaskScheduler",
    "ScheduledTask",
    "StrategySDK",
    "StrategyPlugin",
    "DataSDK",
    "DataProviderPlugin",
    "BrokerSDK",
    "BrokerAdapterPlugin",
    "AISDK",
    "AIModelPlugin",
    "PluginBase",
    "PluginMetadata",
]
