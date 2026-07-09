from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from services.contracts.dto import CashBalanceDTO, OrderDTO, PositionDTO, TradeDTO
from services.reconciliation.models.report import SnapshotReport
from services.reconciliation.snapshot.snapshot_model import Snapshot


class SnapshotService:
    def __init__(self) -> None:
        self.snapshots: Dict[str, Snapshot] = {}

    def create_snapshot(
        self,
        positions: List[PositionDTO],
        cash_balances: List[CashBalanceDTO],
        trades: List[TradeDTO],
        orders: List[OrderDTO],
        metadata: Optional[Dict[str, str]] = None,
    ) -> Snapshot:
        snapshot = Snapshot(
            snapshot_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            positions=positions,
            cash_balances=cash_balances,
            trades=trades,
            orders=orders,
            metadata=metadata or {},
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        return self.snapshots.get(snapshot_id)

    def get_recent_snapshots(self, limit: int = 10) -> List[Snapshot]:
        return sorted(
            self.snapshots.values(),
            key=lambda s: s.timestamp,
            reverse=True,
        )[:limit]

    def generate_report(self, snapshot: Snapshot) -> SnapshotReport:
        return SnapshotReport(
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            total_positions=len(snapshot.positions),
            total_cash_accounts=len(snapshot.cash_balances),
            total_trades=len(snapshot.trades),
            total_orders=len(snapshot.orders),
        )
