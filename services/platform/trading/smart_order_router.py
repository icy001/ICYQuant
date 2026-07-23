"""
Smart order routing engine.
"""


class SmartOrderRouter:

    def route(
        self,
        order,
        venues,
    ):

        return {
            "order":
                order,
            "venue":
                venues[0],
        }