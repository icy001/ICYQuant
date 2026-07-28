from dataclasses import dataclass


@dataclass
class Queue:

    name: str
    messages: list
