"""Test Authority Guardian — authority/delegation monitoring."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest

from services.governance.authority_guardian import AuthorityGuardian
from services.governance.control_trigger import TriggerType


class TestAuthorityGuardian:
    """Test authority guardian behaviors."""

    def test_register_authority(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-001", "PORTFOLIO_A", 50000000)
        assert "AUTH-001" in guardian._authorities

    def test_register_delegation(self):
        guardian = AuthorityGuardian()
        guardian.register_delegation("DEL-001", "AUTH-001", "trader-1", "PORTFOLIO_A", 20000000)
        assert "DEL-001" in guardian._delegations

    def test_check_expired_authority(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-002", "PORTFOLIO_A", 50000000,
                                     expiry=time.time() - 100)  # Already expired
        triggers = guardian.check()
        assert any(t.trigger_type == TriggerType.AUTHORITY_EXPIRY for t in triggers)

    def test_no_breaches_for_active(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-003", "PORTFOLIO_A", 50000000,
                                     expiry=time.time() + 3600)
        triggers = guardian.check()
        assert len(triggers) == 0

    def test_revoke_authority(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-004", "PORTFOLIO_A", 50000000)
        result = guardian.revoke_authority("AUTH-004", "Compromised")
        assert result["success"]

    def test_revoke_cascades_delegations(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-005", "PORTFOLIO_A", 50000000)
        guardian.register_delegation("DEL-002", "AUTH-005", "trader-2", "PORTFOLIO_A", 10000000)
        guardian.register_delegation("DEL-003", "AUTH-005", "trader-3", "PORTFOLIO_A", 10000000)

        # Revoke the authority first
        guardian._authorities["AUTH-005"]["status"] = "REVOKED"

        # Then check — cascade detection should fire
        triggers = guardian.check()
        assert any(t.trigger_type == TriggerType.DELEGATION_CASCADE for t in triggers)

    def test_metrics(self):
        guardian = AuthorityGuardian()
        guardian.register_authority("AUTH-006", "PORTFOLIO_A", 50000000)
        metrics = guardian.get_metrics()
        assert "active_authorities" in metrics
        assert "active_delegations" in metrics
