"""
Research service registry.
"""


class ResearchServiceRegistry:
    def __init__(self):
        self._modules = []

    def add(
        self,
        module,
    ):
        self._modules.append(module)