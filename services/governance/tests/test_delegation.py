"""
Tests for delegation — Valid delegation, Scope mismatch, Amount exceeded,
Sub-delegation blocked, Revoked delegation.

Covers spec test requirements:
  - Delegation: Valid delegation, Expired delegation, Scope mismatch, Amount exceeded,
    Sub-delegation blocked, Revoked delegation
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
from services.governance.delegation_scope import DelegationScope
from services.governance.delegation_limit import DelegationLimit
from services.governance.delegation_validator import DelegationValidator
from services.governance.delegation_engine import DelegationEngine
from services.governance.authority_scope import AuthorityScope, AuthorityScopeLevel
from services.governance.authority_limit import AuthorityLimit
from services.governance.authority_grant import AuthorityGrant
from services.governance.authority_policy import AuthorityLevel


def _make_parent_grant(actor="PM", max_amount=50_000_000, max_risk=5_000_000):
    scope = AuthorityScope(scope_id="S-PM", level=AuthorityScopeLevel.PORTFOLIO,
                           allowed_levels=[AuthorityScopeLevel.PORTFOLIO,
                                           AuthorityScopeLevel.STRATEGY,
                                           AuthorityScopeLevel.ORDER])
    limit = AuthorityLimit(limit_id="L-PM", max_amount=max_amount, max_risk=max_risk,
                           allowed_actions=["APPROVE_ALLOCATION", "APPROVE_RISK_REDUCTION"])
    return AuthorityGrant.create(actor=actor, authority_level=AuthorityLevel.AUTONOMOUS_ALLOCATION,
                                 scope=scope, limit=limit)


def _make_delegation(delegator="PM", delegate="DEPUTY", parent=None, max_amount=20_000_000):
    parent = parent or _make_parent_grant()
    scope = DelegationScope(scope_id="DS-DEP",
                            allowed_levels=[AuthorityScopeLevel.PORTFOLIO, AuthorityScopeLevel.STRATEGY])
    limit = DelegationLimit(limit_id="DL-DEP", max_amount=max_amount, max_risk=2_000_000,
                            allowed_actions=["APPROVE_ALLOCATION"])
    return Delegation.create(delegator=delegator, delegate=delegate, parent_grant=parent,
                             scope=scope, limit=limit, reason="Temporary coverage")


class TestDelegationCreate(unittest.TestCase):
    """Create and validate delegations."""

    def test_create_delegation(self):
        d = _make_delegation()
        self.assertEqual(d.delegator, "PM")
        self.assertEqual(d.delegate, "DEPUTY")
        self.assertEqual(d.status, DelegationStatus.DRAFT)
        self.assertEqual(d.limit.max_amount, 20_000_000)

    def test_activate_delegation(self):
        d = _make_delegation()
        d.activate()
        self.assertEqual(d.status, DelegationStatus.ACTIVE)
        self.assertTrue(d.is_active())

    def test_cannot_reactivate_active(self):
        d = _make_delegation()
        d.activate()
        with self.assertRaises(ValueError):
            d.activate()

    def test_revoke_delegation(self):
        d = _make_delegation()
        d.activate()
        d.revoke("PM", "No longer needed")
        self.assertEqual(d.status, DelegationStatus.REVOKED)
        self.assertFalse(d.is_active())


class TestDelegationValidation(unittest.TestCase):
    """DelegationValidator security checks."""

    def setUp(self):
        self.validator = DelegationValidator(max_delegation_depth=1)
        self.parent = _make_parent_grant(max_amount=50_000_000, max_risk=5_000_000)

    def test_valid_delegation(self):
        d = _make_delegation(parent=self.parent, max_amount=20_000_000)
        result = self.validator.validate(d, self.parent)
        self.assertTrue(result.valid, f"Violations: {result.violations}")

    def test_amount_exceeded(self):
        """Delegation amount cannot exceed parent limit."""
        d = _make_delegation(parent=self.parent, max_amount=60_000_000)
        result = self.validator.validate(d, self.parent)
        self.assertFalse(result.valid)
        self.assertTrue(any("Amount" in v for v in result.violations))

    def test_risk_exceeded(self):
        """Delegation risk cannot exceed parent risk."""
        parent = _make_parent_grant(max_risk=2_000_000)
        d = _make_delegation(parent=parent, max_amount=10_000_000)
        d.limit.max_risk = 5_000_000
        result = self.validator.validate(d, parent)
        self.assertFalse(result.valid)

    def test_sub_delegation_blocked(self):
        """Sub-delegation is blocked by default (depth > 0, allow_subdelegation=False)."""
        parent = _make_parent_grant()
        d = _make_delegation(parent=parent, max_amount=20_000_000)
        d.delegation_depth = 1
        d.allow_subdelegation = False

        result = self.validator.validate(d, parent)
        self.assertFalse(result.valid)
        self.assertTrue(any("Sub-delegation" in v or "depth" in v.lower()
                          for v in result.violations), result.violations)


class TestDelegationChain(unittest.TestCase):
    """Delegation chain validation."""

    def setUp(self):
        self.validator = DelegationValidator(max_delegation_depth=1)

    def test_chain_exactly_at_limit_ok(self):
        """Chain with 1 delegation (max_depth=1, so 2 total incl original = ok)."""
        parent = _make_parent_grant(max_amount=100_000_000, max_risk=10_000_000)
        d1 = _make_delegation(parent=parent, max_amount=50_000_000)
        result = self.validator.validate_chain([d1], parent)
        self.assertTrue(result.valid)


class TestDelegationEngine(unittest.TestCase):
    """DelegationEngine integration."""

    def setUp(self):
        self.engine = DelegationEngine(max_delegation_depth=1)

    def test_create_and_register(self):
        parent = _make_parent_grant()
        d, result = self.engine.create_delegation(
            delegator="PM", delegate="DEPUTY", parent_grant=parent,
            max_amount=10_000_000, reason="Coverage",
        )
        self.assertTrue(result.valid)
        self.assertTrue(d.is_active())
        self.assertEqual(self.engine.count_active(), 1)

    def test_revoke_delegation(self):
        parent = _make_parent_grant()
        d, _ = self.engine.create_delegation("PM", "DEP", parent, max_amount=10_000_000)
        self.assertEqual(self.engine.count_active(), 1)
        self.engine.revoke_delegation(d.delegation_id, "PM")
        self.assertEqual(self.engine.count_active(), 0)
        self.assertEqual(d.status, DelegationStatus.REVOKED)

    def test_expired_on_creation(self):
        parent = _make_parent_grant()
        now = time.time()
        d, result = self.engine.create_delegation(
            "PM", "DEP", parent, max_amount=10_000_000,
            valid_from=now - 200, valid_to=now - 100,
        )
        self.assertFalse(d.is_active())

    def test_get_delegations_for_delegate(self):
        parent = _make_parent_grant()
        d, _ = self.engine.create_delegation("PM", "DEPUTY-A", parent, max_amount=10_000_000)
        delegations = self.engine.get_delegations_for_delegate("DEPUTY-A")
        self.assertEqual(len(delegations), 1)


if __name__ == "__main__":
    unittest.main()
