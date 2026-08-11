"""
Test LineageReconstructor — reconstruction from events, records, and snapshots.
"""

import pytest

from services.governance.lineage_node import LineageNode, LineageNodeType
from services.governance.lineage_edge import LineageEdge, LineageEdgeType
from services.governance.lineage_graph import LineageGraph
from services.governance.lineage_engine import LineageEngine
from services.governance.lineage_snapshot import LineageSnapshot
from services.governance.lineage_reconstructor import LineageReconstructor
from services.governance.lineage_validator import LineageValidator
from services.governance.audit_event_type import AuditEventType
from services.governance.audit_actor import AuditActor
from services.governance.audit_action import AuditAction
from services.governance.audit_event import AuditEvent


class TestReconstructionFromEvents:
    """Test reconstructing lineage from AuditEvents."""

    def test_reconstruct_from_events(self):
        actor = AuditActor.system("test")
        events = [
            AuditEvent("EVT-1", AuditEventType.DECISION_CREATED, "DECISION", "DEC-001",
                       actor, AuditAction.CREATE, correlation_id="CORR-001"),
            AuditEvent("EVT-2", AuditEventType.POLICY_ACTIVATED, "POLICY", "POL-001",
                       actor, AuditAction.ACTIVATE, correlation_id="CORR-001",
                       causation_id="EVT-1"),
            AuditEvent("EVT-3", AuditEventType.AUTHORITY_GRANTED, "AUTHORITY", "AUTH-001",
                       actor, AuditAction.GRANT, correlation_id="CORR-001",
                       causation_id="EVT-2"),
        ]

        recon = LineageReconstructor()
        graph = recon.reconstruct_from_events(events)
        assert graph.node_count == 3

    def test_reconstruct_from_multiple_correlations(self):
        actor = AuditActor.system("test")
        events = [
            AuditEvent("EVT-1", AuditEventType.DECISION_CREATED, "DECISION", "DEC-001",
                       actor, AuditAction.CREATE, correlation_id="CORR-A"),
            AuditEvent("EVT-2", AuditEventType.DECISION_CREATED, "DECISION", "DEC-002",
                       actor, AuditAction.CREATE, correlation_id="CORR-B"),
        ]

        recon = LineageReconstructor()
        graph = recon.reconstruct_from_events(events)
        assert graph.node_count == 2


class TestSnapshotCapture:
    """Test lineage snapshot capture."""

    def test_take_snapshot(self):
        engine = LineageEngine()
        nodes_data = [
            {"node_type": LineageNodeType.MARKET, "entity_type": "MARKET", "entity_id": "NVDA"},
            {"node_type": LineageNodeType.SIGNAL, "entity_type": "SIGNAL", "entity_id": "SIG-001",
             "edge_type": LineageEdgeType.GENERATED},
            {"node_type": LineageNodeType.DECISION, "entity_type": "DECISION", "entity_id": "DEC-001",
             "edge_type": LineageEdgeType.GENERATED},
        ]
        nodes = engine.record_chain(nodes_data, "CORR-001")
        decision_node_id = nodes[-1].node_id

        snap = engine.take_snapshot(decision_node_id, "CORR-001")
        assert snap.snapshot_id.startswith("LSNAP-")
        assert len(snap.nodes) > 0
        assert snap.verify_hash() is True

    def test_snapshot_hash_verification(self):
        engine = LineageEngine()
        n = engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")
        snap = engine.take_snapshot(n.node_id)
        assert snap.verify_hash() is True

    def test_replay_node(self):
        engine = LineageEngine()
        n = engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")
        result = engine.replay_node(n.node_id)
        assert result["hash_valid"] is True


class TestLineageValidator:
    """Test lineage validation."""

    def test_validate_completeness(self):
        engine = LineageEngine()
        nodes_data = [
            {"node_type": LineageNodeType.DECISION, "entity_type": "DECISION", "entity_id": "DEC-001",
             "edge_type": LineageEdgeType.GENERATED},
            {"node_type": LineageNodeType.POLICY, "entity_type": "POLICY", "entity_id": "POL-001",
             "edge_type": LineageEdgeType.EVALUATED_BY},
            {"node_type": LineageNodeType.AUTHORITY, "entity_type": "AUTHORITY", "entity_id": "AUTH-001",
             "edge_type": LineageEdgeType.AUTHORIZED_BY},
        ]
        engine.record_chain(nodes_data, "CORR-001")

        validator = LineageValidator(engine.graph)
        result = validator.validate_completeness("CORR-001")
        assert result["valid"] is True

    def test_validate_orphans(self):
        engine = LineageEngine()
        engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")

        validator = LineageValidator(engine.graph)
        result = validator.validate_orphans()
        assert "valid" in result

    def test_no_cycles(self):
        engine = LineageEngine()
        n1 = engine.record_node(LineageNodeType.MARKET, "MARKET", "NVDA")
        n2 = engine.record_node(LineageNodeType.SIGNAL, "SIGNAL", "SIG-001")
        engine.record_edge(LineageEdgeType.GENERATED, n1.node_id, n2.node_id)

        validator = LineageValidator(engine.graph)
        result = validator.validate_chain_integrity()
        assert result["is_dag"] is True

    def test_validate_all(self):
        engine = LineageEngine()
        engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")

        validator = LineageValidator(engine.graph)
        result = validator.validate_all()
        assert "valid" in result
