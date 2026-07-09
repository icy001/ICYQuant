from abc import ABC, abstractmethod
from typing import Optional


class Strategy(ABC):
    def __init__(self):
        self._context = None
        self._broker = None
        self._data_provider = None
        self._initialized = False

    def initialize(self, context, broker, data_provider):
        self._context = context
        self._broker = broker
        self._data_provider = data_provider
        self._initialized = True

    @abstractmethod
    def on_start(self):
        pass

    @abstractmethod
    def on_bar(self, bar):
        pass

    def on_order(self, order):
        pass

    def on_fill(self, fill):
        pass

    @abstractmethod
    def on_finish(self):
        pass

    def get_context(self):
        return self._context

    def get_broker(self):
        return self._broker

    def get_data_provider(self):
        return self._data_provider

    def is_initialized(self):
        return self._initialized