"""
Runtime builder.
"""

from .backtest_runtime import BacktestRuntime
from .simulation_runtime import SimulationRuntime
from .event_dispatcher import EventDispatcher


class RuntimeBuilder:

    def build(
        self,
        scheduler,
        bus,
    ):

        runtime = SimulationRuntime(
            scheduler,
            EventDispatcher(
                bus,
            ),
        )

        return BacktestRuntime(
            runtime,
        )