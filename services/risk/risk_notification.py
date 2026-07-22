"""
Risk notification service.
"""


class RiskNotificationService:

    def notify(
        self,
        level,
        message,
    ):

        return {
            "level": level,
            "message": message,
        }