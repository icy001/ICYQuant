from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def send_order(self, order):
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_positions(self) -> Dict:
        pass

    @abstractmethod
    def get_account(self) -> Dict:
        pass