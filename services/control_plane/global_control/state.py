"""Global emergency control states (Commit 26 Part 1.5, spec section 3)."""

from enum import Enum


class GlobalControlState(str, Enum):

    """Global control plane state.

    NORMAL
      正常交易。

    RESTRICTED
      限制新增风险（仍允许 Cancel / Reduce / Flatten）。

    KILLED
      全局停止新增风险（New Risk / New Order 关闭，
      Cancel / Reduce / Flatten 仍保留）。

    RECOVERY
      进入恢复流程（KILLED 之后必须经过 RECOVERY 才能回到 NORMAL）。
    """

    NORMAL = "NORMAL"

    RESTRICTED = "RESTRICTED"

    KILLED = "KILLED"

    RECOVERY = "RECOVERY"
