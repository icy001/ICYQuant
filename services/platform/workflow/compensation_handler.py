"""
Compensation handler.
"""


class CompensationHandler:

    def compensate(
        self,
        step,
    ):

        return {
            "rollback": step,
            "status": "DONE",
        }