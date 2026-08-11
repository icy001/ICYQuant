"""
Flow Registry — tracks all active and completed institutional trading flows.

Commit 21 Part 1.1: provides idempotency checking (prevent duplicate flows)
and flow lifecycle querying for audit and monitoring.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .control_flow import ControlFlow
from .control_state import ControlFlowState
from .trading_flow import TradingFlow


@dataclass
class FlowRegistry:
    """Central registry for all trading flows.

    Tracks:
      - Active flows (in progress)
      - Completed flows (terminal)
      - Idempotency keys (duplicate prevention)
      - Flow statistics
    """

    # ── Storage ────────────────────────────────────────────────
    _flows: Dict[str, TradingFlow] = field(default_factory=dict)
    _active_ids: Set[str] = field(default_factory=set)
    _completed_ids: Set[str] = field(default_factory=set)
    _idempotency_keys: Set[str] = field(default_factory=set)
    _flow_id_to_key: Dict[str, str] = field(default_factory=dict)

    # ── Registration ──────────────────────────────────────────

    def register(self, flow: TradingFlow) -> bool:
        """Register a flow. Returns False if flow_id already exists (duplicate)."""
        if flow.flow_id in self._flows:
            return False
        self._flows[flow.flow_id] = flow
        self._active_ids.add(flow.flow_id)
        return True

    def complete(self, flow_id: str) -> None:
        """Mark a flow as completed."""
        if flow_id in self._active_ids:
            self._active_ids.discard(flow_id)
            self._completed_ids.add(flow_id)

    # ── Idempotency ────────────────────────────────────────────

    def register_idempotency_key(self, flow_id: str, key: str) -> bool:
        """Register an idempotency key. Returns False if already seen."""
        if key in self._idempotency_keys:
            return False
        self._idempotency_keys.add(key)
        self._flow_id_to_key[flow_id] = key
        return True

    def is_duplicate(self, key: str) -> bool:
        """Check if an idempotency key has been seen before."""
        return key in self._idempotency_keys

    # ── Queries ────────────────────────────────────────────────

    def get(self, flow_id: str) -> Optional[TradingFlow]:
        return self._flows.get(flow_id)

    def get_control_flow(self, flow_id: str) -> Optional[ControlFlow]:
        flow = self._flows.get(flow_id)
        return flow.control_flow if flow else None

    def get_active(self) -> List[TradingFlow]:
        return [self._flows[fid] for fid in self._active_ids if fid in self._flows]

    def get_completed(self) -> List[TradingFlow]:
        return [self._flows[fid] for fid in self._completed_ids if fid in self._flows]

    def get_by_state(self, state: ControlFlowState) -> List[TradingFlow]:
        result = []
        for flow in self._flows.values():
            if flow.current_state == state:
                result.append(flow)
        return result

    def get_by_strategy(self, strategy_id: str) -> List[TradingFlow]:
        result = []
        for flow in self._flows.values():
            if flow.control_context.strategy_id == strategy_id:
                result.append(flow)
        return result

    def get_by_portfolio(self, portfolio_id: str) -> List[TradingFlow]:
        result = []
        for flow in self._flows.values():
            if flow.control_context.portfolio_id == portfolio_id:
                result.append(flow)
        return result

    # ── Statistics ─────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return {
            "total_flows": len(self._flows),
            "active_flows": len(self._active_ids),
            "completed_flows": len(self._completed_ids),
            "idempotency_keys_registered": len(self._idempotency_keys),
            "by_state": {
                state.name: len(self.get_by_state(state))
                for state in ControlFlowState
            },
        }

    def count(self) -> int:
        return len(self._flows)

    def active_count(self) -> int:
        return len(self._active_ids)

    def completed_count(self) -> int:
        return len(self._completed_ids)

    # ── Cleanup ────────────────────────────────────────────────

    def prune_completed(self, max_age_seconds: float = 3600.0) -> int:
        """Remove completed flows older than max_age_seconds. Returns count removed."""
        now = time.time()
        removed = 0
        to_remove = []
        for fid in list(self._completed_ids):
            flow = self._flows.get(fid)
            if flow and flow.started_at and (now - flow.started_at) > max_age_seconds:
                to_remove.append(fid)

        for fid in to_remove:
            key = self._flow_id_to_key.pop(fid, None)
            if key:
                self._idempotency_keys.discard(key)
            self._completed_ids.discard(fid)
            self._flows.pop(fid, None)
            removed += 1

        return removed

    def reset(self) -> None:
        """Clear all registry data."""
        self._flows.clear()
        self._active_ids.clear()
        self._completed_ids.clear()
        self._idempotency_keys.clear()
        self._flow_id_to_key.clear()
