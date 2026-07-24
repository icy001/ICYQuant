class ExecutionTracker:

    def __init__(self):
        self.executions = {}

    def record(
        self,
        result,
    ):
        self.executions[
            result.order_id
        ] = result

    def get(
        self,
        order_id,
    ):
        return self.executions.get(
            order_id
        )