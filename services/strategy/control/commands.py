"""Strategy control commands.

Every control action performed against a strategy MUST be expressed as a
``StrategyCommand`` and submitted through the strategy control boundary.
No external system is allowed to call ``strategy.start()`` /
``strategy.stop()`` / ``strategy.kill()`` directly, otherwise the
institutional guarantees of the control plane (authorization,
idempotency, audit, replay protection, execution claim, observability)
would be bypassed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

START = "start"
PAUSE = "pause"
RESUME = "resume"
STOP = "stop"
KILL = "kill"

STRATEGY_CONTROL_ACTIONS: frozenset[str] = frozenset(
    {
        START,
        PAUSE,
        RESUME,
        STOP,
        KILL,
    }
)


@dataclass(frozen=True)
class StrategyCommand:
    """A single, governed control command targeting a strategy."""

    command_id: str
    strategy_id: str
    action: str
    principal_id: str
    parameters: dict[str, Any]
    correlation_id: str
    idempotency_key: str


def is_control_action(action: str) -> bool:
    """Return True when ``action`` is a recognised strategy control action."""
    return action in STRATEGY_CONTROL_ACTIONS
