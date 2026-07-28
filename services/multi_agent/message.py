from dataclasses import dataclass


@dataclass
class AgentMessage:

    sender: str

    receiver: str

    task: str

    payload: dict
