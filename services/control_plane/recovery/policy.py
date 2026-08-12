"""Recovery policy (Commit 26 Part 1.5, spec section 14).

Recovery 不能只检查"程序活着"，而必须验证事件总线、账本、仓位、订单、
风险、执行、Venue 与对账是否健康（spec section 15）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPolicy:

    require_no_open_incident: bool = True

    require_position_reconciled: bool = True

    require_orders_reconciled: bool = True

    require_risk_healthy: bool = True

    require_execution_healthy: bool = True

    require_venue_healthy: bool = True

    require_manual_approval: bool = True
