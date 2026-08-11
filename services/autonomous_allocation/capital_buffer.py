"""Capital Buffer — additional safety buffer beyond reserves.

Buffer covers:
- Margin calls
- Execution losses
- Liquidity shocks
- Unexpected drawdowns

Deployable Capital = Total Capital - Required Reserve - Required Buffer
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class BufferLevel(str, Enum):
    """Buffer level severity."""
    LOW = "LOW"  # 3%
    NORMAL = "NORMAL"  # 5%
    ELEVATED = "ELEVATED"  # 8%
    HIGH = "HIGH"  # 12%
    EXTREME = "EXTREME"  # 20%


BUFFER_RATIOS = {
    BufferLevel.LOW: 0.03,
    BufferLevel.NORMAL: 0.05,
    BufferLevel.ELEVATED: 0.08,
    BufferLevel.HIGH: 0.12,
    BufferLevel.EXTREME: 0.20,
}


@dataclass
class BufferState:
    """Current buffer state."""
    level: BufferLevel = BufferLevel.NORMAL
    buffer_ratio: float = 0.05
    buffer_amount: float = 0.0
    margin_call_risk: float = 0.0
    execution_loss_risk: float = 0.0
    liquidity_shock_risk: float = 0.0
    drawdown_risk: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"BufferState[{self.level.value}] "
            f"ratio={self.buffer_ratio:.1%} amount={self.buffer_amount:,.0f}"
        )


class CapitalBuffer:
    """Manages capital buffer for unexpected losses.

    The buffer sits between reserves and deployed capital,
    absorbing shocks before they hit core positions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._level = BufferLevel.NORMAL
        self._total_capital = 0.0
        self._consumed = 0.0

    @property
    def level(self) -> BufferLevel:
        return self._level

    @property
    def buffer_ratio(self) -> float:
        return BUFFER_RATIOS.get(self._level, 0.05)

    @property
    def buffer_amount(self) -> float:
        return max(0.0, self._total_capital * self.buffer_ratio - self._consumed)

    @property
    def consumed(self) -> float:
        return self._consumed

    def set_total_capital(self, capital: float) -> None:
        self._total_capital = capital

    def assess_buffer_level(self,
                            margin_call_risk: float = 0.0,
                            execution_loss_risk: float = 0.0,
                            liquidity_shock_risk: float = 0.0,
                            drawdown_risk: float = 0.0) -> BufferLevel:
        """Determine buffer level from risk indicators."""
        composite = (
            0.30 * margin_call_risk +
            0.25 * execution_loss_risk +
            0.25 * liquidity_shock_risk +
            0.20 * drawdown_risk
        )

        if composite > 0.80:
            level = BufferLevel.EXTREME
        elif composite > 0.60:
            level = BufferLevel.HIGH
        elif composite > 0.40:
            level = BufferLevel.ELEVATED
        elif composite > 0.20:
            level = BufferLevel.NORMAL
        else:
            level = BufferLevel.LOW

        self._level = level
        return level

    def consume(self, loss_amount: float) -> float:
        """Consume buffer to absorb a loss.

        Returns the amount absorbed (may be less than loss if buffer insufficient).
        """
        available = self.buffer_amount
        absorbed = min(loss_amount, available)
        self._consumed += absorbed
        return absorbed

    def replenish(self, amount: float) -> None:
        """Replenish the buffer."""
        self._consumed = max(0.0, self._consumed - amount)

    def reset_consumed(self) -> None:
        """Reset consumed buffer."""
        self._consumed = 0.0

    def get_state(self) -> BufferState:
        """Get current buffer state."""
        return BufferState(
            level=self._level,
            buffer_ratio=self.buffer_ratio,
            buffer_amount=self.buffer_amount,
        )

    def deployable_capital(self, reserve_amount: float) -> float:
        """Compute capital available for deployment after reserve AND buffer."""
        return max(0.0, self._total_capital - reserve_amount - self.buffer_amount)
