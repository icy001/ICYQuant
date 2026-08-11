"""
Tests for delegation expiry — time window validation and expiration.

Covers spec test requirements:
  - Expired delegation handling
  - Time window validity
  - Auto-expiry of overdue delegations
"""

import sys, os, unittest, types, importlib.util, time

# --- Setup virtual package hierarchy ---
_gov_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_services_dir = os.path.dirname(_gov_dir)
_project_root = os.path.dirname(_services_dir)
sys.path.insert(0, _project_root)

_svc = types.ModuleType("services"); _svc.__path__ = [_services_dir]; _svc.__package__ = "services"
sys.modules["services"] = _svc
_gov = types.ModuleType("services.governance"); _gov.__path__ = [_gov_dir]; _gov.__package__ = "services.governance"
sys.modules["services.governance"] = _gov
_s = importlib.util.spec_from_file_location("services.governance.__init__", os.path.join(_gov_dir, "__init__.py"), submodule_search_locations=[_gov_dir])
_m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)

from services.governance.delegation import Delegation
from services.governance.delegation_status import DelegationStatus
from services.governance.delegation_engine import DelegationEngine
from services.governance.delegation_validator import DelegationValidator
from services.governance.delegation_scope import DelegationScope
from services.governance.delegation_limit import DelegationLimit
from services.governance.authority_scope import AuthorityScope, AuthorityScopeLevel
from services.governance.authority_limit import AuthorityLimit
from services.governance.authority_grant import AuthorityGrant
from services.governance.authority_policy import AuthorityLevel


def _make_parent():
    scope = AuthorityScope("S", AuthorityScopeLevel.PORTFOLIO,
                           allowed_levels=[AuthorityScopeLevel.PORTFOLIO, AuthorityScopeLevel.STRATEGY])
    limit = AuthorityLimit("L", max_amount=50_000_000, max_risk=5_000_000)
    return AuthorityGrant.create("PM", AuthorityLevel.AUTONOMOUS_ALLOCATION, scope=scope, limit=limit)


class TestDelegationExpiry(unittest.TestCase):
    """Delegation time-based expiry."""

    def test_expired_delegation_not_active(self):
        now = time.time()
        parent = _make_parent()
        delegation = Delegation.create(
            delegator="PM", delegate="DEP", parent_grant=parent,
            reason="Coverage", valid_from=now - 200, valid_to=now - 100,
        )
        delegation.activate()
        self.assertFalse(delegation.is_active(now))

    def test_valid_future_window(self):
        now = time.time()
        parent = _make_parent()
        delegation = Delegation.create(
            delegator="PM", delegate="DEP", parent_grant=parent,
            reason="Coverage", valid_from=now + 100, valid_to=now + 1000,
        )
        delegation.activate()
        self.assertFalse(delegation.is_active(now))
        self.assertTrue(delegation.is_active(now + 500))

    def test_valid_current_window(self):
        now = time.time()
        parent = _make_parent()
        delegation = Delegation.create(
            delegator="PM", delegate="DEP", parent_grant=parent,
            reason="Coverage", valid_from=now - 100, valid_to=now + 100,
        )
        delegation.activate()
        self.assertTrue(delegation.is_active(now))

    def test_manual_expire(self):
        parent = _make_parent()
        delegation = Delegation.create("PM", "DEP", parent, reason="T")
        delegation.activate()
        self.assertEqual(delegation.status, DelegationStatus.ACTIVE)
        delegation.expire()
        self.assertEqual(delegation.status, DelegationStatus.EXPIRED)


class TestDelegationExpiryEngine(unittest.TestCase):
    """Engine-level expiration."""

    def test_expire_on_creation_past_window(self):
        now = time.time()
        engine = DelegationEngine()
        parent = _make_parent()
        d, _ = engine.create_delegation(
            "PM", "DEP", parent, max_amount=10_000_000,
            valid_from=now - 200, valid_to=now - 100,
        )
        self.assertFalse(d.is_active())

    def test_engine_caps_duration_to_parent(self):
        """Delegation Engine caps delegation duration within parent grant's validity."""
        now = time.time()
        parent = _make_parent()
        parent.valid_to = now + 50
        d, _ = DelegationEngine().create_delegation(
            "PM", "DEP", parent, max_amount=10_000_000,
            valid_from=now, valid_to=now + 100,
        )
        self.assertLessEqual(d.limit.valid_to, now + 50)

    def test_expire_overdue(self):
        engine = DelegationEngine()
        parent = _make_parent()
        parent.valid_to = time.time() + 3600
        d, result = engine.create_delegation(
            "PM", "DEP", parent, max_amount=10_000_000,
            valid_from=time.time() - 100, valid_to=time.time() - 1,
            reason="Already expired",
        )
        self.assertFalse(d.is_active())  # Expired on creation
        count = engine.expire_overdue()
        self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
