"""Global kill switch (Commit 26 Part 1.5, spec sections 7-8, 31).

KILL 是一个明确的 Control Command，而不是业务代码里的
``if emergency: ...``。

核心语义（spec section 10）:

    KILL
     ↓
    BLOCK NEW RISK
     ↓
    PRESERVE RISK REDUCTION

activate() 是幂等的：连续收到多个 KILL 不会产生重复副作用。
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .controller import GlobalControlController
from .state import GlobalControlState


class GlobalControlTransitionError(RuntimeError):

    """Raised when a global control transition is illegal (spec section 33)."""


@dataclass(frozen=True)
class KillSwitchActivation:

    incident_id: UUID | str

    reason: str

    actor: str

    emergency: bool = True


class GlobalKillSwitch:

    def __init__(
        self,
        controller: GlobalControlController,
    ) -> None:

        self.controller = controller

    def activate(
        self,
        activation: KillSwitchActivation,
    ) -> None:

        # 幂等：已经是 KILLED 则直接返回（spec section 31）。
        if (
            self.controller.state
            is GlobalControlState.KILLED
        ):
            return

        self.controller.set_state(
            GlobalControlState.KILLED,
            incident_id=activation.incident_id,
            actor=activation.actor,
            reason=activation.reason,
        )

    def enter_recovery(
        self,
        *,
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
        actor: str = "recovery-orchestrator",
        reason: str = "entering recovery flow",
    ) -> None:

        if (
            self.controller.state
            is GlobalControlState.RECOVERY
        ):
            # 幂等：重复 RECOVERY 不重复启动。
            return

        # 非法迁移保护：只有 KILLED 才能进入 RECOVERY
        # （NORMAL/RESTRICTED 直接进入 RECOVERY 是禁止的）。
        if (
            self.controller.state
            is not GlobalControlState.KILLED
        ):
            raise GlobalControlTransitionError(
                f"cannot enter recovery from "
                f"{self.controller.state.value}",
            )

        self.controller.set_state(
            GlobalControlState.RECOVERY,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
