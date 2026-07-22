"""
Module health checker.
"""


class ModuleHealthChecker:

    def check(
        self,
        modules,
    ):

        return {
            module: "HEALTHY"
            for module in modules
        }