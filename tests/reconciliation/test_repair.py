import pytest

from services.reconciliation.models.difference import PositionDifference
from services.reconciliation.repair.repair_engine import RepairEngine
from services.reconciliation.repair.repair_task import RepairTask


class TestRepairEngine:
    def test_repair_position(self):
        engine = RepairEngine()
        diff = PositionDifference(
            symbol="AAPL",
            expected_quantity=100.0,
            actual_quantity=99.0,
            difference=1.0,
        )
        result = engine.repair_position(diff)
        assert result["type"] == "POSITION_REPAIR"
        assert result["symbol"] == "AAPL"


class TestRepairTask:
    def test_execute_repair(self):
        engine = RepairEngine()
        task = RepairTask(engine)
        position_diffs = [PositionDifference(symbol="AAPL", expected_quantity=100.0, actual_quantity=99.0, difference=1.0)]
        task.execute(position_diffs, [], [], [])
        assert task.status == "COMPLETED"
