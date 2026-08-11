"""Test Governance Monitor — monitoring and detection."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.governance_state import GovernanceRuntimeState
from services.governance.governance_signal import GovernanceSignal, SignalType
from services.governance.governance_threshold import GovernanceThreshold, STANDARD_THRESHOLDS
from services.governance.governance_detector import GovernanceDetector
from services.governance.governance_monitor import GovernanceMonitor
from services.governance.control_trigger import Severity
from services.governance.control_state import GovernanceStateType


class TestGovernanceSignal:
    """Test governance signal creation."""

    def test_create_signal(self):
        sig = GovernanceSignal.create(
            signal_type=SignalType.DRAWDOWN_BREACH,
            severity=Severity.HIGH,
            value=0.07,
            threshold=0.06,
            source="test",
        )
        assert sig.signal_type == SignalType.DRAWDOWN_BREACH
        assert sig.severity == Severity.HIGH
        assert sig.value == 0.07
        assert sig.threshold == 0.06
        assert sig.is_critical is False  # HIGH not CRITICAL
        assert sig.requires_immediate_action is True

    def test_signal_to_dict(self):
        sig = GovernanceSignal.create(
            signal_type=SignalType.VAR_BREACH,
            severity=Severity.MEDIUM,
            value=0.03,
            threshold=0.025,
            source="risk-guardian",
        )
        d = sig.to_dict()
        assert d["signal_type"] == "VAR_BREACH"
        assert d["severity"] == "MEDIUM"


class TestGovernanceThreshold:
    """Test governance threshold evaluation."""

    def test_threshold_breached(self):
        t = GovernanceThreshold(
            threshold_id="T1",
            metric="portfolio_drawdown",
            value=0.06,
            operator=">=",
            target_state=GovernanceStateType.FROZEN,
            severity=Severity.HIGH,
        )
        assert t.is_breached(0.07)
        assert not t.is_breached(0.05)

    def test_threshold_not_breached(self):
        t = GovernanceThreshold(
            threshold_id="T2",
            metric="stress_score",
            value=90,
            operator=">=",
            target_state=GovernanceStateType.FROZEN,
        )
        assert not t.is_breached(80)

    def test_standard_thresholds_have_all_required(self):
        for t in STANDARD_THRESHOLDS:
            assert t.threshold_id
            assert t.metric
            assert t.value >= 0
            assert t.target_state


class TestGovernanceDetector:
    """Test governance detection."""

    def test_detect_drawdown_breach(self):
        detector = GovernanceDetector()
        t = GovernanceThreshold(
            threshold_id="TD1",
            metric="portfolio_drawdown",
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            value=0.06,
            operator=">=",
            target_state=GovernanceStateType.FROZEN,
            severity=Severity.HIGH,
        )
        detector.add_threshold(t)

        state = GovernanceRuntimeState(portfolio_drawdown=0.07)
        signals = detector.detect(state)
        assert len(signals) >= 1
        assert any(s.signal_type == SignalType.DRAWDOWN_BREACH for s in signals)


class TestGovernanceMonitor:
    """Test governance monitor."""

    def test_observe_normal_state(self):
        monitor = GovernanceMonitor()
        state = GovernanceRuntimeState(portfolio_drawdown=0.01)
        result = monitor.observe(state)
        assert "state" in result
        assert "signals" in result
        assert "triggers" in result
        assert "health" in result

    def test_observe_elevated_state(self):
        monitor = GovernanceMonitor()
        state = GovernanceRuntimeState(
            portfolio_drawdown=0.07,
            value_at_risk=0.03,
            stress_score=85,
        )
        result = monitor.observe(state)
        assert result["signals_count"] > 0

    def test_monitor_produces_triggers(self):
        monitor = GovernanceMonitor()
        state = GovernanceRuntimeState(portfolio_drawdown=0.07)
        result = monitor.observe(state)
        assert len(result["triggers"]) > 0

    def test_metrics(self):
        monitor = GovernanceMonitor()
        metrics = monitor.get_metrics()
        assert "monitor_cycles" in metrics
        assert "total_signals" in metrics
