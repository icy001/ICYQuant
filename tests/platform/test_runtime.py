"""
Tests for ICYQuant Runtime, Orchestrator, and Control Plane.
"""

import pytest

from platform.runtime import RuntimeManager, RuntimeState, ModuleRuntime
from platform.orchestrator import PlatformOrchestrator
from platform.control_plane import ControlPlane
from platform.module_registry import ModuleRegistry, ModuleType, ModuleState
from platform.event_router import EventRouter
from platform.workflow_engine import WorkflowEngine
from platform.lifecycle import LifecycleManager, LifecycleState


class TestRuntimeManager:
    """Test runtime module lifecycle management."""

    def test_register_module(self):
        rt = RuntimeManager()
        mod = rt.register_module("test_module")
        assert mod.module_name == "test_module"
        assert mod.state == RuntimeState.STOPPED

    def test_startup_module(self):
        rt = RuntimeManager()
        rt.register_module("test")
        success = rt.startup_module("test")
        assert success is True
        mod = rt.get_runtime("test")
        assert mod.state == RuntimeState.RUNNING

    def test_shutdown_module(self):
        rt = RuntimeManager()
        rt.register_module("test")
        rt.startup_module("test")
        success = rt.shutdown_module("test")
        assert success is True
        mod = rt.get_runtime("test")
        assert mod.state == RuntimeState.STOPPED

    def test_restart_module(self):
        rt = RuntimeManager()
        rt.register_module("test")
        rt.startup_module("test")
        success = rt.restart_module("test")
        assert success is True
        mod = rt.get_runtime("test")
        assert mod.state == RuntimeState.RUNNING
        assert mod.restarts == 1

    def test_pause_and_resume(self):
        rt = RuntimeManager()
        rt.register_module("test")
        rt.startup_module("test")
        assert rt.pause_module("test") is True
        mod = rt.get_runtime("test")
        assert mod.state == RuntimeState.PAUSED
        assert rt.resume_module("test") is True
        assert mod.state == RuntimeState.RUNNING

    def test_hot_reload(self):
        rt = RuntimeManager()
        rt.register_module("test", instance={"old": True})
        rt.startup_module("test")
        success = rt.hot_reload_module("test", new_instance={"new": True})
        assert success is True

    def test_run_startup_sequence(self):
        rt = RuntimeManager()
        rt.register_module("a")
        rt.register_module("b")
        results = rt.run_startup_sequence(["a", "b"])
        assert results["a"] is True
        assert results["b"] is True
        assert rt.get_global_state() == RuntimeState.RUNNING

    def test_run_shutdown_sequence(self):
        rt = RuntimeManager()
        rt.register_module("a")
        rt.register_module("b")
        rt.run_startup_sequence(["a", "b"])
        results = rt.run_shutdown_sequence()
        assert results["a"] is True
        assert rt.get_global_state() == RuntimeState.STOPPED

    def test_get_running(self):
        rt = RuntimeManager()
        rt.register_module("a")
        rt.register_module("b")
        rt.startup_module("a")
        running = rt.get_running()
        assert len(running) == 1
        assert running[0].module_name == "a"

    def test_health_checks(self):
        rt = RuntimeManager()
        rt.register_module("test")
        rt.startup_module("test")
        results = rt.run_health_checks()
        assert results["test"] is True

    def test_get_status(self):
        rt = RuntimeManager()
        rt.register_module("test")
        status = rt.get_status()
        assert "globalState" in status
        assert "totalModules" in status


class TestLifecycleManager:
    """Test lifecycle state transitions."""

    def test_register_module(self):
        lm = LifecycleManager()
        lm.register_module("test")
        assert lm.get_state("test") == LifecycleState.PENDING

    def test_transition(self):
        lm = LifecycleManager()
        lm.register_module("test")
        assert lm.transition("test", LifecycleState.INITIALIZING) is True
        assert lm.get_state("test") == LifecycleState.INITIALIZING

    def test_invalid_transition(self):
        lm = LifecycleManager()
        lm.register_module("test")
        assert lm.transition("test", LifecycleState.RUNNING) is False

    def test_start_lifecycle(self):
        lm = LifecycleManager()
        lm.register_module("test")
        assert lm.start("test") is True
        assert lm.get_state("test") == LifecycleState.RUNNING

    def test_pause_resume(self):
        lm = LifecycleManager()
        lm.register_module("test")
        lm.start("test")
        assert lm.pause("test") is True
        assert lm.get_state("test") == LifecycleState.PAUSED
        assert lm.resume("test") is True
        assert lm.get_state("test") == LifecycleState.RUNNING

    def test_stop_lifecycle(self):
        lm = LifecycleManager()
        lm.register_module("test")
        lm.start("test")
        assert lm.stop("test") is True
        assert lm.get_state("test") == LifecycleState.STOPPED

    def test_get_history(self):
        lm = LifecycleManager()
        lm.register_module("test")
        lm.start("test")
        history = lm.get_history("test")
        assert len(history) > 0

    def test_status(self):
        lm = LifecycleManager()
        lm.register_module("test")
        lm.start("test")
        status = lm.get_status()
        assert "states" in status
        assert "activeModules" in status


class TestPlatformOrchestrator:
    """Test platform orchestrator workflows."""

    def test_trade_sequence(self):
        orch = PlatformOrchestrator()
        result = orch.orchestrate_trade_sequence(
            signal={"symbol": "AAPL", "action": "buy", "quantity": 100},
        )
        assert result["status"] == "completed"
        assert len(result["steps"]) > 0

    def test_trade_with_risk_check(self):
        orch = PlatformOrchestrator()
        result = orch.orchestrate_trade_sequence(
            signal={"symbol": "AAPL"},
            risk_check_fn=lambda s: {"approved": True},
        )
        assert result["status"] == "completed"

    def test_trade_risk_rejected(self):
        orch = PlatformOrchestrator()
        result = orch.orchestrate_trade_sequence(
            signal={"symbol": "AAPL"},
            risk_check_fn=lambda s: {"approved": False, "reason": "Risk limit exceeded"},
        )
        assert result["status"] == "rejected"

    def test_emergency_halt(self):
        orch = PlatformOrchestrator()
        result = orch.orchestrate_emergency_halt("manual")
        assert "paused" in result

    def test_research_to_production(self):
        orch = PlatformOrchestrator()
        result = orch.orchestrate_research_to_production("research_001")
        assert result["status"] == "completed"

    def test_execution_log(self):
        orch = PlatformOrchestrator()
        orch.orchestrate_trade_sequence(signal={"symbol": "AAPL"})
        log = orch.get_execution_log()
        assert len(log) > 0

    def test_status(self):
        orch = PlatformOrchestrator()
        status = orch.get_status()
        assert "totalExecutions" in status


class TestControlPlane:
    """Test control plane operations."""

    def test_pause_trading(self):
        cp = ControlPlane()
        result = cp.pause_trading("test")
        assert "paused" in result

    def test_resume_trading(self):
        cp = ControlPlane()
        result = cp.resume_trading("test")
        assert "resumed" in result

    def test_cancel_all_orders(self):
        cp = ControlPlane()
        result = cp.cancel_all_orders("emergency")
        assert result["cancelled"] is True

    def test_emergency_shutdown(self):
        cp = ControlPlane()
        result = cp.emergency_shutdown("critical")
        assert "shutdown" in result

    def test_module_command(self):
        cp = ControlPlane()
        result = cp.module_command("trading", "status")
        assert isinstance(result, dict)

    def test_control_log(self):
        cp = ControlPlane()
        cp.pause_trading("test")
        log = cp.get_log()
        assert len(log) > 0

    def test_status(self):
        cp = ControlPlane()
        status = cp.get_status()
        assert "totalActions" in status
