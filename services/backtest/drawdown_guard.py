"""
Drawdown protection.
"""


class DrawdownGuard:
    def check(
        self,
        drawdown,
        rule,
    ):
        return drawdown <= rule.max_drawdown