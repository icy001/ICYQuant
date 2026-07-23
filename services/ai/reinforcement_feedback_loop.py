"""
Reinforcement feedback loop.
"""


class ReinforcementFeedbackLoop:

    def calculate_reward(
        self,
        pnl,
        drawdown,
    ):

        return pnl - drawdown