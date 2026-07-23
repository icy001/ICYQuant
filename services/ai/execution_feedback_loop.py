"""
Execution feedback loop.
"""


class ExecutionFeedbackLoop:

    def __init__(self):

        self.records = []

    def record(
        self,
        execution_result,
    ):

        self.records.append(
            execution_result
        )

    def history(self):

        return self.records