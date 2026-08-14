"""Strategy command arbitration.

In production several actors (operator, risk engine, automation) may submit
control commands almost simultaneously.  Without arbitration the commands
would be executed in an arbitrary order, which is dangerous for a trading
system.  ``StrategyCommandArbiter`` therefore picks the command with the
highest control priority - ``KILL`` always wins.
"""

from __future__ import annotations

from services.strategy.control.commands import StrategyCommand

#: Lower value = lower precedence.  ``kill`` has the highest priority and
#: must be executed before any normal lifecycle command.
CONTROL_PRIORITY: dict[str, int] = {
    "start": 10,
    "resume": 20,
    "pause": 30,
    "stop": 40,
    "kill": 100,
}


class StrategyCommandArbiter:
    """Selects the winning strategy control command among candidates."""

    def select(self, commands: list[StrategyCommand]) -> StrategyCommand:
        """Return the command with the highest control priority.

        Raises ``ValueError`` when ``commands`` is empty or contains an
        unknown action.
        """
        if not commands:
            raise ValueError("no commands to arbitrate")

        def priority(command: StrategyCommand) -> int:
            try:
                return CONTROL_PRIORITY[command.action]
            except KeyError:
                raise ValueError(
                    f"unknown control action: {command.action}"
                ) from None

        return max(commands, key=priority)
