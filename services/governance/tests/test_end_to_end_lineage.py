"""
End-to-End Lineage Test — full decision chain simulation.

Simulates: MARKET → SIGNAL → STRATEGY → DECISION →
           POLICY → AUTHORITY → APPROVAL → CERTIFICATE →
           ORDER → EXECUTION → TRADE → LEDGER

Verifies complete lineage integrity.
"""

import pytest

from services.governance.lineage_engine import LineageEngine
from services.governance.lineage_node import LineageNodeType
from services.governance.lineage_edge import LineageEdgeType
from services.governance.lineage_validator import LineageValidator
from services.governance.lineage_exporter import LineageExporter
from services.governance.audit_engine import AuditEngine
from services.governance.audit_event_type import AuditEventType
from services.governance.audit_actor import AuditActor
from services.governance.audit_action import AuditAction
from services.governance.audit_outcome import AuditOutcome
from services.governance.decision_snapshot import DecisionSnapshot
from services.governance.decision_record import DecisionRecord, DecisionRecordStatus


class TestEndToEndLineage:
    """Full end-to-end lineage simulation."""

    def test_full_decision_chain_lineage(self):
        """Simulate complete lineage from Market to Ledger."""
        engine = LineageEngine()
        corr_id = "E2E-TEST-001"

        # 1. Market → Signal → Strategy → Decision
        market = engine.record_node(
            LineageNodeType.MARKET, "MARKET", "NVDA",
            state={"price": 182.40, "volume": "+34%"},
            correlation_id=corr_id,
        )
        factor = engine.record_node(
            LineageNodeType.FACTOR, "FACTOR", "MOMENTUM",
            state={"value": 0.92},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.GENERATED, market.node_id, factor.node_id)

        signal = engine.record_node(
            LineageNodeType.SIGNAL, "SIGNAL", "SIG-001",
            state={"type": "LONG", "confidence": 0.87},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.GENERATED, factor.node_id, signal.node_id)

        strategy = engine.record_node(
            LineageNodeType.STRATEGY, "STRATEGY", "AI-MOMENTUM-V7",
            state={"version": "v7"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.USED, signal.node_id, strategy.node_id)

        decision = engine.record_node(
            LineageNodeType.DECISION, "DECISION", "DEC-001",
            state={"side": "BUY", "amount": 25_000_000, "instrument": "NVDA"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.GENERATED, strategy.node_id, decision.node_id)

        # 2. Policy → Authority → Approval
        policy = engine.record_node(
            LineageNodeType.POLICY, "POLICY", "CAPITAL_POLICY",
            state={"version": "v4", "verdict": "REQUIRE_APPROVAL", "limit": 20_000_000},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.EVALUATED_BY, decision.node_id, policy.node_id)

        authority = engine.record_node(
            LineageNodeType.AUTHORITY, "AUTHORITY", "AUTH-PM-001",
            state={"scope": "PORTFOLIO_A", "limit": 50_000_000},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.AUTHORIZED_BY, policy.node_id, authority.node_id)

        approval = engine.record_node(
            LineageNodeType.APPROVAL, "APPROVAL", "APR-001",
            state={"approver": "PORTFOLIO_MANAGER", "status": "APPROVED"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.APPROVED_BY, authority.node_id, approval.node_id)

        guard = engine.record_node(
            LineageNodeType.DECISION_GUARD, "GUARD", "GUARD-001",
            state={"result": "PASS"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.VALIDATED_BY, approval.node_id, guard.node_id)

        # 3. Certificate → Order → Execution → Trade
        cert = engine.record_node(
            LineageNodeType.CERTIFICATE, "CERTIFICATE", "CERT-001",
            state={"hash": "sha256:aaa"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.GENERATED, guard.node_id, cert.node_id)

        order = engine.record_node(
            LineageNodeType.ORDER, "ORDER", "ORD-001",
            state={"side": "BUY", "quantity": 137100, "instrument": "NVDA"},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.CREATED_FROM, cert.node_id, order.node_id)

        execution = engine.record_node(
            LineageNodeType.EXECUTION, "EXECUTION", "EXE-001",
            state={"filled": 137100, "avg_price": 182.40},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.EXECUTED_AS, order.node_id, execution.node_id)

        trade = engine.record_node(
            LineageNodeType.TRADE, "TRADE", "TRD-001",
            state={"quantity": 137100, "price": 182.40},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.GENERATED, execution.node_id, trade.node_id)

        position = engine.record_node(
            LineageNodeType.POSITION, "POSITION", "POS-001",
            state={"instrument": "NVDA", "quantity": 137100},
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.SETTLED_TO, trade.node_id, position.node_id)

        ledger = engine.record_node(
            LineageNodeType.LEDGER, "LEDGER", "LDR-001",
            correlation_id=corr_id,
        )
        engine.record_edge(LineageEdgeType.SETTLED_TO, position.node_id, ledger.node_id)

        # ── Verification ──

        # 1. Graph structure
        assert engine.node_count == 14
        assert engine.edge_count == 14

        # 2. Completeness
        result = engine.check_completeness(corr_id)
        assert result["complete"] is True

        # 3. No orphans
        orphan_result = engine.detect_orphans()
        assert orphan_result["orphan_count"] == 0

        # 4. No broken edges
        assert len(orphan_result["broken_edges"]) == 0

        # 5. Full lineage resolution from TRADE
        full = engine.resolve_full(trade.node_id)
        assert full["upstream_count"] >= 10
        assert full["downstream_count"] >= 2

        # 6. Backward resolution from TRADE → MARKET
        backward = engine.resolve_backward(trade.node_id)
        assert backward["direction"] == "BACKWARD"
        assert len(backward["chain"]) >= 10

        # 7. Forward resolution from MARKET → LEDGER
        forward = engine.resolve_forward(market.node_id)
        assert forward["direction"] == "FORWARD"
        assert len(forward["chain"]) >= 10

    def test_lineage_query(self):
        """Test lineage query with filters."""
        engine = LineageEngine()
        corr_id = "QUERY-TEST-001"

        for i in range(3):
            engine.record_node(
                LineageNodeType.DECISION, "DECISION", f"DEC-{i:03d}",
                correlation_id=corr_id,
            )

        nodes = engine.query_by_correlation(corr_id)
        assert len(nodes) == 3

        dec_nodes = engine.graph.get_nodes_by_entity("DECISION", "DEC-000")
        assert len(dec_nodes) == 1

    def test_lineage_exporter_dot(self):
        """Test lineage DOT export."""
        engine = LineageEngine()
        market = engine.record_node(LineageNodeType.MARKET, "MARKET", "NVDA")
        decision = engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")
        engine.record_edge(LineageEdgeType.GENERATED, market.node_id, decision.node_id)

        exporter = LineageExporter(engine.graph)
        dot = exporter.to_dot()
        assert "digraph" in dot
        assert "NVDA" in dot

        summary = exporter.to_summary()
        assert summary["total_nodes"] == 2
        assert summary["total_edges"] == 1

    def test_audit_engine_integration(self):
        """Test AuditEngine records events for lineage."""
        engine = AuditEngine()
        actor = AuditActor.strategy("ai-momentum-v7", "v7")

        engine.record_event(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="DECISION",
            entity_id="DEC-E2E-001",
            actor=actor,
            action=AuditAction.CREATE,
            reason="Long NVDA signal",
            correlation_id="E2E-AUDIT-001",
        )

        events = engine.get_events_by_correlation("E2E-AUDIT-001")
        assert len(events) == 1
        assert events[0].entity_id == "DEC-E2E-001"

    def test_lineage_validator_full(self):
        """Validate the full end-to-end graph."""
        engine = LineageEngine()
        corr_id = "VALIDATE-TEST-001"

        engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001", correlation_id=corr_id)
        engine.record_node(LineageNodeType.POLICY, "POLICY", "POL-001", correlation_id=corr_id)
        engine.record_node(LineageNodeType.AUTHORITY, "AUTHORITY", "AUTH-001", correlation_id=corr_id)

        validator = LineageValidator(engine.graph)
        result = validator.validate_all(correlation_id=corr_id)
        assert "valid" in result
