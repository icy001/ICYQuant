"""
Domain registry.
"""


class DomainRegistry:

    def __init__(self):

        self.modules = {}

    def register(
        self,
        name,
        module,
    ):

        self.modules[name] = module

    def get(
        self,
        name,
    ):

        return self.modules.get(name)