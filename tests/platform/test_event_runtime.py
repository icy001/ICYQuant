from services.platform.events import EventStore


def test_event_store():

    store = EventStore()

    store.save("event")

    assert len(
        store.load()
    ) == 1