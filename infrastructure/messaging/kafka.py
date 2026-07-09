from abc import ABC, abstractmethod


class KafkaAdapter(ABC):
    @abstractmethod
    def publish(self, topic: str, message: dict) -> None:
        ...

    @abstractmethod
    def subscribe(self, topic: str):
        ...


class MockKafkaAdapter(KafkaAdapter):
    def __init__(self) -> None:
        self._messages = {}

    def publish(self, topic: str, message: dict) -> None:
        if topic not in self._messages:
            self._messages[topic] = []
        self._messages[topic].append(message)

    def subscribe(self, topic: str):
        return self._messages.get(topic, [])
