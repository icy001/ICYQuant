"""
Institutional research platform.
"""


class LegacyResearchPlatform:
    def __init__(
        self,
        container,
    ):
        self.container = container

    def start(self):
        return True