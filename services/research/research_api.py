"""
Unified research API.
"""


class ResearchAPI:

    def __init__(
        self,
        platform,
    ):

        self.platform = platform

    def run(
        self,
        workflow,
        notebook,
        dependencies,
        modules,
    ):

        return self.platform.start(
            workflow,
            notebook,
            dependencies,
            modules,
        )