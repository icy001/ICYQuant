"""
Gradual rollout strategy.
"""


class RolloutStrategy:


    def __init__(

        self,

        percentage=0,

    ):

        self.percentage = percentage



    def allowed(

        self,

        value,

    ):

        return value < self.percentage