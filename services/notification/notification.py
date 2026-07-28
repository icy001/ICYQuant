from dataclasses import dataclass


@dataclass
class Notification:
    notification_id: str
    user_id: str
    message: str
    channel: str