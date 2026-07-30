from dataclasses import dataclass


@dataclass
class Message:
    message_id: str
    topic: str
    payload: dict
    status: str
