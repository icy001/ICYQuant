"""
Zero downtime deployment.
"""


class RollingUpdate:

    def deploy(
        self,
        version,
    ):
        return {
            "version":
                version,
            "status":
                "rolling"
        }