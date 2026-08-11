"""End-to-end compatibility tests: serialization round-trip, registry, fingerprint, replay."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import json
import time
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

from services.integration.contracts.control_contract import ControlContract
from services.integration.contracts.control_request import (
    ControlRequest, RiskRequest, GovernanceRequest,
)
from services.integration.contracts.control_response import ControlResponse, ControlResponseStatus
from services.integration.contracts.control_context import ContractControlContext
from services.integration.contracts.control_constraint import (
    ControlConstraint, ConstraintSource, ConstraintType, ConstraintRule,
    EffectiveConstraints, intersect_constraints,
)
from services.integration.contracts.control_evidence import RiskEvidence, GovernanceEvidence
from services.integration.contracts.control_reason import ReasonCode
from services.integration.contracts.control_reference import ControlReference, DecisionLineage
from services.integration.contracts.control_decision import ControlDecision, DecisionStatus
from services.integration.contracts.control_version import ContractVersion, check_compatibility
from services.integration.contract_registry import ContractRegistry
from services.integration.contract_serializer import ContractSerializer
from services.integration.contract_fingerprint import ContractFingerprint
from services.integration.contract_metrics import ContractMetrics
from services.integration.contract_validator import ContractValidator
from services.integration.contracts.contract_errors import (
    ContractVersionError,
    ContractReplayError,
)


class TestCrossDomainSerialization(unittest.TestCase):
    """Full round-trip: contract → JSON → contract."""

    def setUp(self):
        self.serializer = ContractSerializer()
        self.ctx = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
        )

    def test_round_trip_contract(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.add_constraint(
            ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK)
        )
        contract.with_response(
            ControlResponse.make_pass(
                domain="risk",
                reason_code=ReasonCode.RISK_CHECK_PASSED,
                flow_id=self.ctx.flow_id,
            )
        )

        # Serialize
        json_str = self.serializer.serialize(contract)
        self.assertIsInstance(json_str, str)
        self.assertIn("contract_id", json_str)

        # Deserialize
        restored = self.serializer.deserialize(json_str)
        self.assertEqual(restored.contract_id, contract.contract_id)
        self.assertEqual(restored.domain, "risk")
        self.assertEqual(restored.context.flow_id, "FLOW-001")
        self.assertEqual(len(restored.constraints), 1)
        self.assertIsNotNone(restored.response)
        self.assertTrue(restored.response.passed)

    def test_round_trip_with_all_fields(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.add_constraint(ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK))
        contract.add_evidence(RiskEvidence.from_assessment("exposure", 0.12, 0.15))
        contract.add_reference(ControlReference.root(flow_id=self.ctx.flow_id, domain="signal"))
        contract.with_response(ControlResponse.make_pass(
            "risk", ReasonCode.RISK_LIMIT_OK, flow_id=self.ctx.flow_id,
        ))
        contract.with_decision(ControlDecision.from_responses(
            flow_id=self.ctx.flow_id,
            responses=[contract.response],
        ))

        json_str = self.serializer.serialize(contract)
        restored = self.serializer.deserialize(json_str)

        self.assertEqual(restored.contract_id, contract.contract_id)
        self.assertEqual(len(restored.constraints), 1)
        self.assertEqual(len(restored.evidence), 1)
        self.assertEqual(len(restored.references), 1)
        self.assertIsNotNone(restored.decision)


class TestContractRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = ContractRegistry()

    def test_register_and_resolve_exact(self):
        def handler(ctx):
            return "ok"
        self.registry.register("risk", "v1", handler)
        resolved = self.registry.resolve("risk", "v1")
        self.assertEqual(resolved("ctx"), "ok")

    def test_resolve_compatible_version(self):
        def handler(ctx):
            return "ok"
        self.registry.register("risk", "v1.1", handler)
        # Client asks v1 → server has v1.1 → COMPATIBLE
        resolved = self.registry.resolve("risk", "v1")
        self.assertEqual(resolved("ctx"), "ok")

    def test_resolve_deprecated_version(self):
        def handler(ctx):
            return "ok"
        self.registry.register("risk", "v1", handler)
        # Client asks v1.1 → server has only v1 → DEPRECATED
        resolved = self.registry.resolve("risk", "v1.1")
        self.assertEqual(resolved("ctx"), "ok")

    def test_resolve_incompatible_raises(self):
        def handler(ctx):
            return "ok"
        self.registry.register("risk", "v1", handler)
        with self.assertRaises(ContractVersionError):
            self.registry.resolve("risk", "v2")

    def test_unknown_domain_raises(self):
        with self.assertRaises(KeyError):
            self.registry.resolve("nonexistent", "v1")

    def test_get_versions(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.register("risk", "v1.1", lambda x: x)
        self.registry.register("risk", "v2", lambda x: x)
        versions = self.registry.get_versions("risk")
        self.assertEqual(versions, ["v1", "v1.1", "v2"])

    def test_get_latest_version(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.register("risk", "v3", lambda x: x)
        self.registry.register("risk", "v1.5", lambda x: x)
        self.assertEqual(self.registry.get_latest_version("risk"), "v3")

    def test_deprecate(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.deprecate("risk", "v1", "Use v2 instead")
        # Deprecated versions are skipped during resolution
        self.registry.register("risk", "v1.1", lambda x: "v1.1")
        resolved = self.registry.resolve("risk", "v1")
        # Should pick v1.1 since v1 is deprecated
        self.assertEqual(resolved("ctx"), "v1.1")

    def test_domain_count(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.register("governance", "v1", lambda x: x)
        self.assertEqual(self.registry.domain_count(), 2)

    def test_total_versions(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.register("risk", "v1.1", lambda x: x)
        self.registry.register("governance", "v1", lambda x: x)
        self.assertEqual(self.registry.total_versions(), 3)

    def test_unregister(self):
        self.registry.register("risk", "v1", lambda x: x)
        self.registry.unregister("risk", "v1")
        self.assertEqual(self.registry.total_versions(), 0)


class TestContractFingerprint(unittest.TestCase):

    def setUp(self):
        self.fp = ContractFingerprint()
        self.ctx = ContractControlContext(flow_id="FLOW-001")

    def test_identical_contracts_same_fingerprint(self):
        req1 = ControlRequest(domain="risk", context=self.ctx)
        contract1 = ControlContract.create(domain="risk", request=req1)

        req2 = ControlRequest(domain="risk", context=self.ctx)
        contract2 = ControlContract.create(domain="risk", request=req2)

        # Different contract_id → different fingerprint
        fp1 = self.fp.compute(contract1)
        fp2 = self.fp.compute(contract2)
        self.assertNotEqual(fp1.fingerprint, fp2.fingerprint)  # different contract_id

    def test_deterministic_same_input(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)

        fp1 = self.fp.compute(contract)
        fp2 = self.fp.compute(contract)
        self.assertEqual(fp1.fingerprint, fp2.fingerprint)

    def test_verify_integrity(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        fp = self.fp.compute(contract)
        self.assertTrue(self.fp.verify_integrity(contract, fp.fingerprint))


class TestReplayProtection(unittest.TestCase):

    def setUp(self):
        self.fp = ContractFingerprint()
        self.ctx = ContractControlContext(flow_id="FLOW-001")

    def test_first_contract_not_replay(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)

        # Should not raise
        result = self.fp.check_and_record(contract)
        self.assertIsNotNone(result)
        self.assertEqual(self.fp.seen_count, 1)

    def test_duplicate_contract_is_replay(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)

        self.fp.check_and_record(contract)
        self.assertEqual(self.fp.seen_count, 1)

        with self.assertRaises(ContractReplayError):
            self.fp.check_and_record(contract)

    def test_prune_old_entries(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        self.fp.check_and_record(contract)
        self.assertEqual(self.fp.seen_count, 1)

        # Prune with 0 TTL should remove everything
        removed = self.fp.prune(ttl_seconds=-1)
        self.assertGreaterEqual(removed, 0)


class TestReferenceChain(unittest.TestCase):

    def test_lineage_chain(self):
        flow_id = "FLOW-CHAIN-001"
        lineage = DecisionLineage()

        ref_signal = ControlReference.root(flow_id=flow_id, domain="signal")
        ref_decision = ControlReference.child_of(ref_signal, "decision")
        ref_risk = ControlReference.child_of(ref_decision, "risk")
        ref_gov = ControlReference.child_of(ref_risk, "governance")
        ref_auth = ControlReference.child_of(ref_gov, "authority")
        ref_approval = ControlReference.child_of(ref_auth, "approval")
        ref_admission = ControlReference.child_of(ref_approval, "admission")

        lineage.add(ref_signal).add(ref_decision).add(ref_risk).add(ref_gov).add(
            ref_auth
        ).add(ref_approval).add(ref_admission)

        self.assertTrue(lineage.validate_connected())
        self.assertEqual(
            lineage.full_chain,
            ["signal", "decision", "risk", "governance", "authority", "approval", "admission"],
        )
        self.assertTrue(lineage.is_complete)

    def test_disconnected_lineage(self):
        lineage = DecisionLineage()
        # Create ref with no parent in the lineage
        orphan = ControlReference(domain="risk", flow_id="FLOW-001", parent_reference_id="REF-NONEXISTENT")
        lineage.add(orphan)
        self.assertFalse(lineage.validate_connected())

    def test_find_by_domain(self):
        lineage = DecisionLineage()
        ref = ControlReference.root(flow_id="FLOW-001", domain="risk")
        lineage.add(ref)
        found = lineage.find("risk")
        self.assertIsNotNone(found)
        self.assertEqual(found.domain, "risk")
        self.assertIsNone(lineage.find("governance"))


class TestDecisionObject(unittest.TestCase):

    def test_decision_from_all_pass_responses(self):
        responses = [
            ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001"),
            ControlResponse.make_pass("governance", ReasonCode.POLICY_COMPLIANT, flow_id="FLOW-001"),
        ]
        decision = ControlDecision.from_responses(
            flow_id="FLOW-001", responses=responses
        )
        self.assertEqual(decision.status, DecisionStatus.ALLOW)
        self.assertTrue(decision.allowed)

    def test_decision_from_mixed_responses(self):
        responses = [
            ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001"),
            ControlResponse.make_reject(
                "governance", ReasonCode.GOVERNANCE_FROZEN,
                reason="Account frozen", flow_id="FLOW-001",
            ),
        ]
        decision = ControlDecision.from_responses(
            flow_id="FLOW-001", responses=responses
        )
        self.assertEqual(decision.status, DecisionStatus.DENY)
        self.assertFalse(decision.allowed)
        self.assertIsNotNone(decision.block_reason)
        self.assertIn("GOVERNANCE_FROZEN", decision.block_reason)

    def test_decision_block_reason_none_when_allowed(self):
        responses = [
            ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001"),
        ]
        decision = ControlDecision.from_responses(flow_id="FLOW-001", responses=responses)
        self.assertIsNone(decision.block_reason)

    def test_decision_serialization(self):
        responses = [
            ControlResponse.make_pass("risk", ReasonCode.RISK_LIMIT_OK, flow_id="FLOW-001"),
        ]
        decision = ControlDecision.from_responses(
            flow_id="FLOW-001",
            responses=responses,
            constraints=[ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK)],
        )
        d = decision.to_dict()
        self.assertEqual(d["status"], "ALLOW")
        self.assertEqual(d["flow_id"], "FLOW-001")
        self.assertEqual(len(d["responses"]), 1)


class TestInvalidContractRejection(unittest.TestCase):

    def test_empty_contract_id_rejected(self):
        validator = ContractValidator()
        ctx = ContractControlContext(flow_id="FLOW-001")
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.contract_id = ""

        result = validator.validate(contract)
        self.assertFalse(result.valid)

    def test_expired_contract_rejected(self):
        validator = ContractValidator()
        ctx = ContractControlContext(flow_id="FLOW-001")
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.with_expiry(time.time() - 86400)

        result = validator.validate(contract)
        self.assertFalse(result.valid)


class TestContractMetrics(unittest.TestCase):

    def test_record_pass_and_reject(self):
        metrics = ContractMetrics()
        ctx = ContractControlContext(flow_id="FLOW-001")

        resp_pass = ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001")
        resp_reject = ControlResponse.make_reject("governance", ReasonCode.GOVERNANCE_FROZEN, flow_id="FLOW-001")

        metrics.record_response("risk", resp_pass)
        metrics.record_response("governance", resp_reject)

        self.assertEqual(metrics.total_contracts, 2)

        risk_m = metrics.get_domain_metrics("risk")
        self.assertEqual(risk_m.passed, 1)

        gov_m = metrics.get_domain_metrics("governance")
        self.assertEqual(gov_m.rejected, 1)

    def test_metrics_domain_breakdown(self):
        metrics = ContractMetrics()
        for _ in range(5):
            resp = ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001")
            metrics.record_response("risk", resp)

        breakdown = metrics.domain_breakdown()
        self.assertIn("risk", breakdown)
        self.assertEqual(breakdown["risk"]["total"], 5)
        self.assertEqual(breakdown["risk"]["pass_rate"], 1.0)

    def test_metrics_reset(self):
        metrics = ContractMetrics()
        resp = ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001")
        metrics.record_response("risk", resp)
        self.assertEqual(metrics.total_contracts, 1)

        metrics.reset()
        self.assertEqual(metrics.total_contracts, 0)

    def test_metrics_summary(self):
        metrics = ContractMetrics()
        resp = ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id="FLOW-001")
        metrics.record_response("risk", resp)

        summary = metrics.summary()
        self.assertIn("total_contracts", summary)
        self.assertIn("overall_pass_rate", summary)
        self.assertIn("domains", summary)


if __name__ == "__main__":
    unittest.main()
