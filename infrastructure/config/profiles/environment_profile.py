"""
Environment profile manager.
"""


class EnvironmentProfile:

    PROFILES = [
        "development",
        "testing",
        "staging",
        "production"
    ]

    def exists(
        self,
        name,
    ):
        return name in self.PROFILES