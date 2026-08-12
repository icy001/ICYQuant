"""Global control policy (Commit 26 Part 1.5, spec section 5).

核心原则：KILLED 并不代表"所有交易 API 全部关闭"，而是：

    New Risk        ❌
    New Orders      ❌
    Cancel          ✅
    Reduce          ✅
    Flatten         ✅

其中 Cancel / Reduce / Flatten 的保留与否可由 policy 配置。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GlobalControlPolicy:

    killed_allow_cancel: bool = True

    killed_allow_reduce: bool = True

    killed_allow_emergency_flatten: bool = True

    recovery_requires_validation: bool = True

    recovery_requires_manual_approval: bool = True
