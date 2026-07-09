from .simulator import SimExecution


class ExecutionService:
    def __init__(self, simulator: SimExecution = None):
        self.simulator = simulator or SimExecution()

    def execute_order(self, order):
        return self.simulator.execute(order)