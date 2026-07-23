"""
Notification abstraction.
"""


class Notifier:

    def send(
        self,
        alert,
    ):
        return {
            "sent":
                True,
            "alert":
                alert

        }