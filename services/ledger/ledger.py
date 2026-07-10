from typing import List, Optional

from .event import LedgerEvent
from .store import EventStore, InMemoryEventStore
from .projector import Projection


class Ledger:
    def __init__(self, store: Optional[EventStore] = None):
        self.store: EventStore = store or InMemoryEventStore()
        self.projectors: List[Projection] = []

    def register_projector(self, projector: Projection) -> None:
        self.projectors.append(projector)

    def record(self, event: LedgerEvent) -> None:
        self.store.append(event)
        for projector in self.projectors:
            projector.apply(event)

    def replay(self) -> List[LedgerEvent]:
        for projector in self.projectors:
            projector.reset()

        events = self.store.replay()
        for event in events:
            for projector in self.projectors:
                projector.apply(event)

        return events

    def snapshot(self) -> dict:
        snapshot = {}
        for projector in self.projectors:
            if hasattr(projector, 'state'):
                snapshot[type(projector).__name__] = projector.state
        return snapshot

    def restore(self, snapshot: dict) -> None:
        for projector in self.projectors:
            name = type(projector).__name__
            if name in snapshot:
                projector.state = snapshot[name]