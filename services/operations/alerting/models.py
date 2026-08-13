"""Alert state (Commit 27 Part 1.3, spec section 5).

完整生命周期：

    TRIGGER -> FIRING -> ACKNOWLEDGED -> RESOLVED

如果规则暂时不应该产生告警：

    FIRING -> SUPPRESSED
"""

from enum import Enum


class AlertState(str, Enum):

    FIRING = "FIRING"

    ACKNOWLEDGED = "ACKNOWLEDGED"

    RESOLVED = "RESOLVED"

    SUPPRESSED = "SUPPRESSED"
