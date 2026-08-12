"""Global emergency control (Commit 26 Part 1.5).

Kill Switch 负责"立即停止新增风险"，Recovery 负责"安全地恢复交易"。
"""

from .controller import GlobalControlController
from .decision import GlobalControlDecision
from .kill_switch import (
    GlobalControlTransitionError,
    GlobalKillSwitch,
    KillSwitchActivation,
)
from .policy import GlobalControlPolicy
from .state import GlobalControlState

__all__ = [
    "GlobalControlController",
    "GlobalControlDecision",
    "GlobalControlPolicy",
    "GlobalControlState",
    "GlobalControlTransitionError",
    "GlobalKillSwitch",
    "KillSwitchActivation",
]
