"""
Policy enforcement engine.
"""


class PolicyEngine:

    def evaluate(
        self,
        policy,
        context,
    ):

        return {
            "allowed": True,
            "policy": policy,
        }