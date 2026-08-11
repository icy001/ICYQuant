"""Tests for ContractVersion parsing and comparison."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

# ── Virtual package bootstrap ──────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc

_svc_dir = os.path.join(_ws, "services")
_int_dir = os.path.join(_svc_dir, "integration")
_ctr_dir = os.path.join(_int_dir, "contracts")

if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod

if "services.integration.contracts" not in sys.modules:
    _pkg = types.ModuleType("services.integration.contracts")
    _pkg.__path__ = [_ctr_dir]
    sys.modules["services.integration.contracts"] = _pkg

for _dir, _pkg_name, _names in [
    (_ctr_dir, "services.integration.contracts", [
        "contract_errors", "control_version", "control_reason",
        "control_context", "control_request", "control_response",
        "control_evidence", "control_constraint", "control_reference",
        "control_decision", "control_contract",
    ]),
    (_int_dir, "services.integration", [
        "contract_registry", "contract_validator", "contract_serializer",
        "contract_fingerprint", "contract_metrics",
    ]),
]:
    for _name in _names:
        _fp = os.path.join(_dir, f"{_name}.py")
        if not os.path.exists(_fp):
            continue
        _spec = importlib.util.spec_from_file_location(f"{_pkg_name}.{_name}", _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[f"{_pkg_name}.{_name}"] = _m
        _spec.loader.exec_module(_m)

from services.integration.contracts.control_version import (
    ContractVersion,
    VersionCompatibility,
    check_compatibility,
)


class TestContractVersionParsing(unittest.TestCase):

    def test_parse_v1(self):
        v = ContractVersion.parse("v1")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 0)

    def test_parse_v1_1(self):
        v = ContractVersion.parse("v1.1")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 1)

    def test_parse_v2(self):
        v = ContractVersion.parse("v2")
        self.assertEqual(v.major, 2)
        self.assertEqual(v.minor, 0)

    def test_parse_plain_number(self):
        v = ContractVersion.parse("3")
        self.assertEqual(v.major, 3)
        self.assertEqual(v.minor, 0)

    def test_parse_plain_float(self):
        v = ContractVersion.parse("2.5")
        self.assertEqual(v.major, 2)
        self.assertEqual(v.minor, 5)

    def test_parse_stripped(self):
        v = ContractVersion.parse("  v1.2  ")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)

    def test_parse_uppercase(self):
        v = ContractVersion.parse("V3")
        self.assertEqual(v.major, 3)
        self.assertEqual(v.minor, 0)

    def test_parse_default(self):
        v = ContractVersion.parse("")
        self.assertEqual(v.major, 0)
        self.assertEqual(v.minor, 0)


class TestContractVersionStr(unittest.TestCase):

    def test_str_major_only(self):
        self.assertEqual(str(ContractVersion(1, 0)), "v1")

    def test_str_minor(self):
        self.assertEqual(str(ContractVersion(1, 1)), "v1.1")

    def test_str_large(self):
        self.assertEqual(str(ContractVersion(3, 7)), "v3.7")


class TestContractVersionComparison(unittest.TestCase):

    def test_equal(self):
        self.assertEqual(ContractVersion(1, 0), ContractVersion(1, 0))

    def test_less_than_major(self):
        self.assertLess(ContractVersion(1, 0), ContractVersion(2, 0))

    def test_less_than_minor(self):
        self.assertLess(ContractVersion(1, 0), ContractVersion(1, 1))

    def test_greater_than(self):
        self.assertGreater(ContractVersion(2, 0), ContractVersion(1, 9))

    def test_sorting(self):
        versions = [
            ContractVersion(2, 0),
            ContractVersion(1, 5),
            ContractVersion(1, 0),
            ContractVersion(3, 0),
        ]
        sorted_versions = sorted(versions)
        self.assertEqual([str(v) for v in sorted_versions], ["v1", "v1.5", "v2", "v3"])

    def test_hashable(self):
        s = {ContractVersion(1, 0), ContractVersion(1, 0), ContractVersion(2, 0)}
        self.assertEqual(len(s), 2)


class TestVersionCompatibility(unittest.TestCase):

    def test_exact_match_compatible(self):
        result = check_compatibility(ContractVersion(1, 0), ContractVersion(1, 0))
        self.assertEqual(result, VersionCompatibility.COMPATIBLE)

    def test_server_newer_minor_compatible(self):
        """Client asks v1, server supports v1.1 → COMPATIBLE (server is newer)"""
        result = check_compatibility(ContractVersion(1, 0), ContractVersion(1, 1))
        self.assertEqual(result, VersionCompatibility.COMPATIBLE)

    def test_client_newer_minor_compatible(self):
        """Client asks v1.1, server supports v1 → DEPRECATED (client is ahead)"""
        result = check_compatibility(ContractVersion(1, 1), ContractVersion(1, 0))
        self.assertEqual(result, VersionCompatibility.DEPRECATED)

    def test_different_major_incompatible(self):
        result = check_compatibility(ContractVersion(1, 0), ContractVersion(2, 0))
        self.assertEqual(result, VersionCompatibility.INCOMPATIBLE)

    def test_v2_to_v1_incompatible(self):
        result = check_compatibility(ContractVersion(2, 0), ContractVersion(1, 0))
        self.assertEqual(result, VersionCompatibility.INCOMPATIBLE)

    def test_usable_property(self):
        self.assertTrue(VersionCompatibility.COMPATIBLE.is_usable)
        self.assertTrue(VersionCompatibility.DEPRECATED.is_usable)
        self.assertFalse(VersionCompatibility.INCOMPATIBLE.is_usable)


class TestVersionCompatibilityEnum(unittest.TestCase):

    def test_labels(self):
        self.assertEqual(VersionCompatibility.COMPATIBLE.label, "COMPATIBLE")
        self.assertEqual(VersionCompatibility.INCOMPATIBLE.label, "INCOMPATIBLE")
        self.assertEqual(VersionCompatibility.DEPRECATED.label, "DEPRECATED")


class TestVersionFactoryMethods(unittest.TestCase):

    def test_v1(self):
        self.assertEqual(ContractVersion.v1(), ContractVersion(1, 0))

    def test_v1_1(self):
        self.assertEqual(ContractVersion.v1_1(), ContractVersion(1, 1))

    def test_v2(self):
        self.assertEqual(ContractVersion.v2(), ContractVersion(2, 0))


if __name__ == "__main__":
    unittest.main()
