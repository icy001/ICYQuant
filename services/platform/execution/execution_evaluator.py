"""
Execution evaluator.
"""


class ExecutionEvaluator:

    def evaluate(
        self,
        execution_result,
    ):

        return {
            "success":
                execution_result is not None,
            "result":
                execution_result,
        }