"""
Production Operations Layer (Commit 27 Part 1.1).

Operations = 看清楚系统发生了什么
Control    = 决定系统允许做什么
Recovery   = 决定系统什么时候可以重新做

重要边界（spec sections 16-18）：

1. Operational Health 不是 Trading Health：
   Service = HEALTHY 不代表 Trading = SAFE（Position != Ledger 时
   Trading State = NOT SAFE）。

2. Operations 只负责 Observe，不执行控制：
   正确路径是 Operations -> Health Signal -> Incident -> Control Plane
   -> Kill / Pause / Failover。Observability 代码绝不能偷偷拥有交易
   控制权限。
"""

from .health import ServiceHealthMonitor
from .models import (
    OperationalSnapshot,
    ServiceDependency,
    ServiceHealth,
    ServiceIdentity,
    ServiceState,
)
from .registry import (
    RegisteredService,
    ServiceRegistry,
    validate_dependency,
)
from .snapshot import OperationalSnapshotBuilder

__all__ = [
    "OperationalSnapshot",
    "OperationalSnapshotBuilder",
    "RegisteredService",
    "ServiceDependency",
    "ServiceHealth",
    "ServiceHealthMonitor",
    "ServiceIdentity",
    "ServiceRegistry",
    "ServiceState",
    "validate_dependency",
]
