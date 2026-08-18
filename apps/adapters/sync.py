"""Sync engine - pulls broker state into the Account cache and reconciles
the cached Account Domain state against the adapter (broker) truth.
"""

from __future__ import annotations

from datetime import datetime, timezone

from apps.adapters.registry import AdapterRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncEngine:
    def __init__(self, registry: AdapterRegistry) -> None:
        self.registry = registry

    # ------------------------------------------------------------------
    # per-account sync (the four sync surfaces)
    # ------------------------------------------------------------------

    def sync_account(self, account_id: str) -> dict:
        account = self.registry.get_account(account_id)
        adapter = self.registry.adapter_for(account.broker_id)
        account = adapter.sync_account(account_id)
        return account

    def sync_positions(self, account_id: str) -> list:
        account = self.registry.get_account(account_id)
        adapter = self.registry.adapter_for(account.broker_id)
        positions = adapter.sync_positions(account_id)
        account.positions = list(positions)
        return list(positions)

    def sync_orders(self, account_id: str) -> list:
        account = self.registry.get_account(account_id)
        adapter = self.registry.adapter_for(account.broker_id)
        orders = adapter.sync_orders(account_id)
        account.orders = list(orders)
        return list(orders)

    def sync_executions(self, account_id: str) -> list:
        account = self.registry.get_account(account_id)
        adapter = self.registry.adapter_for(account.broker_id)
        executions = adapter.sync_executions(account_id)
        account.executions = list(executions)
        return list(executions)

    # ------------------------------------------------------------------
    # full sync
    # ------------------------------------------------------------------

    def sync_all(self) -> dict:
        """Pull every account's balance, positions, orders and executions."""
        report = {
            "accounts": 0,
            "positions": 0,
            "orders": 0,
            "executions": 0,
            "timestamp": _now(),
        }
        for broker in self.registry.brokers():
            for account_id in broker.account_ids:
                self.sync_account(account_id)
                report["positions"] += len(self.sync_positions(account_id))
                report["orders"] += len(self.sync_orders(account_id))
                report["executions"] += len(self.sync_executions(account_id))
                report["accounts"] += 1
        return report

    # ------------------------------------------------------------------
    # reconciliation (cached Account Domain vs adapter / broker truth)
    # ------------------------------------------------------------------

    def reconcile(self) -> dict:
        rows = []
        for account in self.registry.accounts():
            adapter = self.registry.adapter_for(account.broker_id)
            live_balance = adapter.get_balance(account.account_id)
            live_positions = adapter.get_positions(account.account_id)
            live_orders = adapter.get_orders(account.account_id)
            live_executions = adapter.get_executions(account.account_id)

            differences = []
            if abs(account.equity - live_balance.equity) > 0.01:
                differences.append("equity")
            if abs(account.cash - live_balance.cash) > 0.01:
                differences.append("cash")
            if len(account.positions) != len(live_positions):
                differences.append("positions")
            if len(account.orders) != len(live_orders):
                differences.append("orders")
            if len(account.executions) != len(live_executions):
                differences.append("executions")

            rows.append(
                {
                    "account_id": account.account_id,
                    "broker_id": account.broker_id,
                    "market": account.market,
                    "status": "CONSISTENT" if not differences else "INCONSISTENT",
                    "expected": {
                        "equity": account.equity,
                        "cash": account.cash,
                        "positions": len(account.positions),
                        "orders": len(account.orders),
                        "executions": len(account.executions),
                    },
                    "actual": {
                        "equity": live_balance.equity,
                        "cash": live_balance.cash,
                        "positions": len(live_positions),
                        "orders": len(live_orders),
                        "executions": len(live_executions),
                    },
                    "differences": differences,
                    "checked_at": _now(),
                }
            )

        inconsistent = [r for r in rows if r["status"] == "INCONSISTENT"]
        return {
            "status": "CONSISTENT" if not inconsistent else "INCONSISTENT",
            "accounts": rows,
            "checked_at": _now(),
        }
