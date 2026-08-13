"""Service dependency model (Commit 27 Part 1.1, spec section 8).

交易系统最大的特点：服务之间不是孤立的。

    Strategy -> Risk -> Order -> Execution -> Venue

因此需要显式描述依赖，为后续 Incident Correlation 打基础
（spec section 20：Event Bus 故障 -> Ledger / Position / OMS / Risk
可能全部受到影响，需要理解 Root Dependency）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDependency:

    source_service: str

    target_service: str

    required: bool = True

    description: str = ""
