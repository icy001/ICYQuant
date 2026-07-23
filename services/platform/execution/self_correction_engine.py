"""
Self correction engine.
"""


class SelfCorrectionEngine:

    def correct(
        self,
        evaluation,
    ):

        if not evaluation["success"]:

            return {
                "action": "retry"
            }

        return {
            "action": "continue"
        }