"""
Application lifecycle controller.
"""


class LifecycleManager:

    def start(self):
        return {
            "status":
                "started"
        }

    def stop(self):
        return {
            "status":
                "stopped"
        }