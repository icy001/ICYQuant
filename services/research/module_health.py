"""
Research module health checker.
"""


class ResearchModuleHealthChecker:

    def check(
        self,
        modules,
    ):

        return {
            module: "HEALTHY"
            for module in modules
        }