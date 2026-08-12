"""EscalationDecision — immutable escalation outcome."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.control_plane.incident.escalation.decision import EscalationDecision
from services.control_plane.incident.escalation.level import EscalationLevel

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


class TestEscalationDecision:
    def test_escalation_decision_fields(self):
        decision = EscalationDecision(
            should_escalate=True,
            current_level=EscalationLevel.L2,
            target_level=EscalationLevel.L3,
            reason="incident exceeded escalation timeout",
            triggered_at=NOW,
        )
        assert decision.should_escalate is True
        assert decision.current_level == EscalationLevel.L2
        assert decision.target_level == EscalationLevel.L3
        assert decision.reason == "incident exceeded escalation timeout"
        assert decision.triggered_at == NOW

    def test_no_escalation_decision(self):
        decision = EscalationDecision(
            should_escalate=False,
            current_level=EscalationLevel.L1,
            target_level=None,
            reason="escalation timeout not reached",
            triggered_at=NOW,
        )
        assert decision.should_escalate is False
        assert decision.target_level is None

    def test_decision_is_frozen(self):
        decision = EscalationDecision(
            should_escalate=False,
            current_level=EscalationLevel.L1,
            target_level=None,
            reason="ok",
            triggered_at=NOW,
        )
        with pytest.raises(FrozenInstanceError):
            decision.should_escalate = True
