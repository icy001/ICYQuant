"""Strategy domain layer.

The domain package holds pure domain concepts that describe *what* a
strategy is, independent of any control mechanism.  In particular it
contains the strategy control state which expresses the position of a
strategy inside the institutional control boundary.
"""

from services.strategy.domain.control_state import StrategyControlState

__all__ = ["StrategyControlState"]
