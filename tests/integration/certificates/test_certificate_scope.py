"""Tests for CertificateScope — scope definition and binding verification."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest
import time

# ── Bootstrap: register services / services.integration as namespace packages ──
_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_int_dir = os.path.join(_ws, "services", "integration")
_cert_dir = os.path.join(_int_dir, "certificates")

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc
if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod
if "services.integration.certificates" not in sys.modules:
    _pkg = types.ModuleType("services.integration.certificates")
    _pkg.__path__ = [_cert_dir]
    sys.modules["services.integration.certificates"] = _pkg

for _name in [
    "certificate_errors", "certificate_status", "certificate_scope",
    "certificate_claim", "certificate_evidence", "certificate_signature",
    "certificate_fingerprint", "pre_trade_certificate", "certificate_builder",
    "certificate_validator", "certificate_verifier",
]:
    _fp = os.path.join(_cert_dir, f"{_name}.py")
    if not os.path.exists(_fp):
        continue
    _mod_name = f"services.integration.certificates.{_name}"
    if _mod_name in sys.modules:
        continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

for _name in [
    "certificate_lifecycle", "certificate_registry", "certificate_metrics",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    if not os.path.exists(_fp):
        continue
    _mod_name = f"services.integration.{_name}"
    if _mod_name in sys.modules:
        continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

from services.integration.certificates.certificate_scope import (
    CertificateScope, ScopeGranularity, ConsumptionMode,
)

# ═══════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════


class TestCertificateScopeCreation(unittest.TestCase):
    """Scope creation and defaults."""

    def test_default_scope(self):
        scope = CertificateScope()
        self.assertTrue(scope.scope_id.startswith("SCOPE-"))
        self.assertEqual(scope.symbol, "")
        self.assertEqual(scope.side, "")

    def test_factory_for_order(self):
        scope = CertificateScope.for_order(
            account_id="ACC-001", symbol="NVDA", side="BUY",
            max_quantity=1000, max_notional=180000,
            venue="NASDAQ", strategy_id="STRAT-001",
        )
        self.assertEqual(scope.symbol, "NVDA")
        self.assertEqual(scope.side, "BUY")
        self.assertEqual(scope.max_quantity, 1000)
        self.assertEqual(scope.granularity, ScopeGranularity.ORDER)
        self.assertEqual(scope.consumption_mode, ConsumptionMode.ONE_TIME)

    def test_factory_for_symbol(self):
        scope = CertificateScope.for_symbol(
            account_id="ACC-001", symbol="AAPL", side="SELL",
            max_quantity=5000, venue="NASDAQ",
        )
        self.assertEqual(scope.granularity, ScopeGranularity.SYMBOL)
        self.assertEqual(scope.consumption_mode, ConsumptionMode.QUANTITY_CAPPED)


class TestCertificateScopeBinding(unittest.TestCase):
    """Scope binding checks."""

    def setUp(self):
        self.scope = CertificateScope.for_order(
            account_id="ACC-001", symbol="NVDA", side="BUY",
            max_quantity=1000, venue="NASDAQ",
        )

    def test_symbol_match(self):
        self.assertTrue(self.scope.check_symbol("NVDA"))
        self.assertTrue(self.scope.check_symbol("nvda"))

    def test_symbol_mismatch(self):
        self.assertFalse(self.scope.check_symbol("AAPL"))

    def test_side_match(self):
        self.assertTrue(self.scope.check_side("BUY"))
        self.assertTrue(self.scope.check_side("buy"))

    def test_side_mismatch(self):
        self.assertFalse(self.scope.check_side("SELL"))

    def test_venue_match(self):
        self.assertTrue(self.scope.check_venue("NASDAQ"))
        self.assertTrue(self.scope.check_venue("nasdaq"))

    def test_venue_mismatch(self):
        self.assertFalse(self.scope.check_venue("NYSE"))


class TestCertificateScopeLimits(unittest.TestCase):
    """Scope limit and consumption checks."""

    def setUp(self):
        self.scope = CertificateScope.for_order(
            account_id="ACC-001", symbol="NVDA", side="BUY",
            max_quantity=1000, max_notional=180000,
        )

    def test_quantity_within_limit(self):
        self.assertTrue(self.scope.check_quantity(500))
        self.assertTrue(self.scope.check_quantity(1000))

    def test_quantity_exceeds_limit(self):
        self.assertFalse(self.scope.check_quantity(1500))

    def test_notional_within_limit(self):
        self.assertTrue(self.scope.check_notional(100000))

    def test_notional_exceeds_limit(self):
        self.assertFalse(self.scope.check_notional(200000))

    def test_quantity_remaining(self):
        self.assertEqual(self.scope.quantity_remaining, 1000)
        self.scope.consume_quantity(300)
        self.assertEqual(self.scope.quantity_consumed, 300)
        self.assertEqual(self.scope.quantity_remaining, 700)

    def test_consume_quantity_exceeded_raises(self):
        with self.assertRaises(ValueError):
            self.scope.consume_quantity(1500)

    def test_consume_notional_exceeded_raises(self):
        with self.assertRaises(ValueError):
            self.scope.consume_notional(200000)


class TestCertificateScopeExpiry(unittest.TestCase):
    """Scope expiry tests."""

    def test_active_within_window(self):
        scope = CertificateScope(expires_at=time.time() + 3600)
        self.assertTrue(scope.is_active())

    def test_inactive_past_expiry(self):
        scope = CertificateScope(expires_at=time.time() - 1)
        self.assertFalse(scope.is_active())

    def test_active_no_expiry(self):
        scope = CertificateScope()
        self.assertTrue(scope.is_active())


class TestNoLimitScope(unittest.TestCase):
    """Scope with no limits set."""

    def setUp(self):
        self.scope = CertificateScope(
            account_id="ACC-001", symbol="NVDA", side="BUY",
        )

    def test_no_max_quantity_allows_all(self):
        self.assertIsNone(self.scope.quantity_remaining)
        self.assertTrue(self.scope.check_quantity(999999))

    def test_no_max_notional_allows_all(self):
        self.assertIsNone(self.scope.notional_remaining)
        self.assertTrue(self.scope.check_notional(999999))


if __name__ == "__main__":
    unittest.main()
