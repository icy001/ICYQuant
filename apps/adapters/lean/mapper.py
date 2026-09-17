"""Contract → LEAN payload translation.

Pure functions, no I/O: the payload written to disk is exactly what the
LEAN algorithm reads back, so it must be JSON-safe and self-describing.
"""
from __future__ import annotations

from typing import Any

from .contract import StrategyContract, StrategyIntent

__all__ = [
    "contract_to_lean_payload",
    "intent_to_lean_order",
    "normalize_side",
]


def normalize_side(side: str) -> str:
    """Upper-case and validate an order side."""
    normalized = str(side).upper()

    if normalized not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported order side: {normalized}")

    return normalized


def intent_to_lean_order(intent: StrategyIntent) -> dict[str, Any]:
    """One intent as the JSON order record the LEAN algorithm consumes."""
    intent.validate()

    return {
        "symbol": intent.symbol,
        "side": normalize_side(intent.side),
        "quantity": int(intent.quantity),
        "limit_price": (
            float(intent.limit_price) if intent.limit_price is not None else None
        ),
        "stop_price": (
            float(intent.stop_price) if intent.stop_price is not None else None
        ),
        "strategy_id": intent.strategy_id,
        "signal_id": intent.signal_id,
        "timestamp": intent.timestamp,
        "target_weight": intent.target_weight,
        "metadata": intent.metadata,
    }


def contract_to_lean_payload(contract: StrategyContract) -> dict[str, Any]:
    """The full ``strategy_contract.json`` document."""
    contract.validate()

    return {
        "contract_version": contract.contract_version,
        "strategy_id": contract.strategy_id,
        "mode": contract.mode,
        "initial_cash": float(contract.initial_cash),
        "symbols": list(contract.symbols),
        "orders": [intent_to_lean_order(intent) for intent in contract.intents],
        "metadata": contract.metadata,
    }
