from services.eventstore.repository import EventRepository
from services.eventstore.storage import InMemoryEventStorage


class TestEventRepository:
    def test_repository_initializes_empty(self):
        repo = EventRepository()
        assert len(repo.get_all()) == 0

    def test_repository_append_event(self):
        repo = EventRepository()
        event = {"event_id": "1", "type": "TEST"}
        repo.append(event)
        assert len(repo.get_all()) == 1
        assert repo.get_all()[0]["event_id"] == "1"

    def test_repository_append_multiple_events(self):
        repo = EventRepository()
        repo.append({"event_id": "1", "type": "TEST"})
        repo.append({"event_id": "2", "type": "TEST"})
        assert len(repo.get_all()) == 2


class TestInMemoryEventStorage:
    def test_storage_initializes_empty(self):
        storage = InMemoryEventStorage()
        assert len(storage.load_all()) == 0

    def test_storage_save_and_load(self):
        storage = InMemoryEventStorage()
        from dataclasses import dataclass

        @dataclass
        class TestEvent:
            event_id: str
            type: str

        event = TestEvent(event_id="test-1", type="TRADE")
        storage.save(event)
        loaded = storage.load("test-1")
        assert loaded.event_id == "test-1"

    def test_storage_load_all(self):
        storage = InMemoryEventStorage()
        from dataclasses import dataclass

        @dataclass
        class TestEvent:
            event_id: str
            type: str

        storage.save(TestEvent(event_id="1", type="TRADE"))
        storage.save(TestEvent(event_id="2", type="TRADE"))
        events = storage.load_all()
        assert len(events) == 2
