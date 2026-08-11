"""
Tests for authority limits — Valid, Invalid, Scope mismatch, Amount exceeded,
Risk exceeded, Expired, Revoked.

Covers spec test requirements:
  - Authority: Valid, Invalid, Scope mismatch, Amount exceeded, Risk exceeded, Expired, Revoked
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

from services.governance.authority_scope import AuthorityScope, AuthorityScopeLevel
from services.governance.authority_limit import AuthorityLimit
from services.governance.authority_grant import AuthorityGrant
from services.governance.authority_policy import AuthorityLevel
from services.governance.authority_revocation import AuthorityRevocationRegistry


def _make_scope(level=AuthorityScopeLevel.PORTFOLIO, allowed=None):
    return AuthorityScope(
        scope_id="SC-TEST", level=level,
        allowed_levels=allowed or [level]
    )


def _make_limit(max_amount=20_000_000, max_risk=2_000_000, actions=None):
    return AuthorityLimit(
        limit_id="LIM-TEST", max_amount=max_amount, max_risk=max_risk,
        allowed_actions=actions or ["APPROVE_ALLOCATION"]
    )


def _make_grant(actor="test_user", authority=AuthorityLevel.AUTONOMOUS_ALLOCATION, scope=None, limit=None):
    return AuthorityGrant.create(
        actor=actor, authority_level=authority, scope=scope or _make_scope(),
        limit=limit or _make_limit()
    )


class TestAuthorityLimit(unittest.TestCase):
    """AuthorityLimit checks."""

    def test_allows_amount(self):
        limit = _make_limit(max_amount=20_000_000)
        self.assertTrue(limit.allows_amount(10_000_000))
        self.assertTrue(limit.allows_amount(20_000_000))
        self.assertFalse(limit.allows_amount(21_000_000))

    def test_allows_risk(self):
        limit = _make_limit(max_risk=2_000_000)
        self.assertTrue(limit.allows_risk(1_000_000))
        self.assertFalse(limit.allows_risk(3_000_000))

    def test_allows_action(self):
        limit = _make_limit(actions=["APPROVE_ALLOCATION", "APPROVE_RISK_REDUCTION"])
        self.assertTrue(limit.allows_action("APPROVE_ALLOCATION"))
        self.assertFalse(limit.allows_action("APPROVE_LEVERAGE_INCREASE"))

    def test_allows_action_no_restriction(self):
        limit = AuthorityLimit(limit_id="L", max_amount=10_000_000)
        self.assertTrue(limit.allows_action("ANYTHING"))

    def test_exceeded(self):
        limit = _make_limit(max_amount=10_000_000)
        violations = limit.exceeded(amount=12_000_000)
        self.assertIn("amount", violations)

    def test_is_active(self):
        now = time.time()
        limit = AuthorityLimit(limit_id="L", valid_from=now + 10, valid_to=now + 100)
        self.assertFalse(limit.is_active(now))
        self.assertTrue(limit.is_active(now + 50))


class TestAuthorityScope(unittest.TestCase):
    """AuthorityScope hierarchy checks."""

    def test_covers_self(self):
        scope = _make_scope(AuthorityScopeLevel.PORTFOLIO)
        self.assertTrue(scope.covers(AuthorityScopeLevel.PORTFOLIO))

    def test_covers_descendant(self):
        scope = _make_scope(AuthorityScopeLevel.PORTFOLIO)
        self.assertTrue(scope.covers(AuthorityScopeLevel.STRATEGY))

    def test_cannot_cover_parent(self):
        scope = _make_scope(AuthorityScopeLevel.STRATEGY)
        self.assertFalse(scope.covers(AuthorityScopeLevel.PORTFOLIO))

    def test_excluded_level(self):
        scope = _make_scope(AuthorityScopeLevel.PORTFOLIO, allowed=[AuthorityScopeLevel.PORTFOLIO, AuthorityScopeLevel.STRATEGY])
        scope.excluded_levels = [AuthorityScopeLevel.STRATEGY]
        self.assertTrue(scope.covers(AuthorityScopeLevel.PORTFOLIO))
        self.assertFalse(scope.covers(AuthorityScopeLevel.STRATEGY))

    def test_global_covers_all(self):
        scope = _make_scope(AuthorityScopeLevel.GLOBAL)
        for level in AuthorityScopeLevel:
            if level != AuthorityScopeLevel.GLOBAL:
                self.assertTrue(scope.covers(level), f"GLOBAL should cover {level.name}")


class TestAuthorityGrant(unittest.TestCase):
    """AuthorityGrant validity and revocation."""

    def test_factory_create(self):
        grant = _make_grant("PM-User")
        self.assertEqual(grant.actor, "PM-User")
        self.assertTrue(grant.is_valid())
        self.assertTrue(grant.can_approve_amount(10_000_000))
        self.assertFalse(grant.can_approve_amount(30_000_000))

    def test_revoke(self):
        grant = _make_grant("PM-User")
        self.assertTrue(grant.active)
        grant.revoke("admin", "Transferred")
        self.assertFalse(grant.active)
        self.assertIsNotNone(grant.revoked_at)
        self.assertFalse(grant.is_valid())

    def test_cannot_approve_risk_exceeded(self):
        grant = _make_grant(limit=_make_limit(max_risk=1_000_000))
        self.assertTrue(grant.can_approve_risk(500_000))
        self.assertFalse(grant.can_approve_risk(2_000_000))

    def test_expired_grant(self):
        now = time.time()
        grant = AuthorityGrant.create("user", AuthorityLevel.AUTONOMOUS_ALLOCATION,
                                       valid_from=now - 200, valid_to=now - 100)
        self.assertFalse(grant.is_valid(now))

    def test_revoked_grant_invalid(self):
        grant = _make_grant("user")
        grant.revoke("admin", "test")
        self.assertFalse(grant.is_valid())


class TestAuthorityRevocationRegistry(unittest.TestCase):
    """Authority Revocation Registry."""

    def test_record_revocation(self):
        grant = _make_grant("user")
        registry = AuthorityRevocationRegistry()
        self.assertFalse(registry.is_revoked(grant.grant_id))

        rev = registry.revoke_grant(grant, "admin", "Position change")
        self.assertTrue(registry.is_revoked(grant.grant_id))
        self.assertFalse(grant.active)

    def test_get_revocations_for_actor(self):
        g1 = _make_grant("actor-A")
        g2 = _make_grant("actor-B")
        g3 = _make_grant("actor-A")
        registry = AuthorityRevocationRegistry()
        registry.revoke_grant(g1, "admin", "a")
        registry.revoke_grant(g2, "admin", "b")
        registry.revoke_grant(g3, "admin", "c")
        revs_a = registry.get_revocations_for_actor("actor-A")
        self.assertEqual(len(revs_a), 2)


if __name__ == "__main__":
    unittest.main()
