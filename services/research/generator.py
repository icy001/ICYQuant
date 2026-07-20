"""
Walk-forward window generator.
"""

from .window import WalkForwardWindow


class WindowGenerator:
    def generate(self):
        return [
            WalkForwardWindow(
                "2023-01",
                "2023-06",
                "2023-07",
                "2023-09",
            )
        ]