from services.notification import *


def test_notification_service():
    service = NotificationService(
        NotificationManager(
            NotificationRepository(),
            AlertEngine(),
            ChannelRouter()
        )
    )

    notification = Notification(
        "N001",
        "USER001",
        "Trade executed",
        NotificationChannel.EMAIL
    )

    result = service.notify(notification)

    assert result.message == "Trade executed"