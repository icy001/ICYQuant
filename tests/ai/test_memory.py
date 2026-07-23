from datetime import datetime

from services.ai import (
    MemoryRecord,
    MemoryStore,
)


def test_memory_store():

    store = MemoryStore()

    record = MemoryRecord(
        "M001",
        "research",
        "NVDA AI demand increasing",
        datetime.utcnow(),
        {},
    )

    store.save(
        record
    )

    assert store.get(
        "M001"
    ).content == "NVDA AI demand increasing"