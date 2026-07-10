from services.ledger import (
    LedgerEvent,
    LedgerEventType,
    MemoryEventStore,
)


def create_event():

    return LedgerEvent(

        event_type=
            LedgerEventType.ORDER_FILLED,


        aggregate_id=
            "ACCOUNT-001",


        payload={

            "symbol":
                "NVDA",

            "quantity":
                100,

            "price":
                150.0,

        },

    )




def test_append_event():


    store = MemoryEventStore()


    event = create_event()


    store.append(
        event
    )


    assert store.count() == 1


    assert (
        store.get(
            event.event_id
        )
        ==
        event
    )




def test_stream_by_aggregate():


    store = MemoryEventStore()


    event = create_event()


    store.append(
        event
    )


    events = store.stream(
        "ACCOUNT-001"
    )


    assert len(events) == 1


    assert (
        events[0]
        ==
        event
    )




def test_all_events_order():


    store = MemoryEventStore()


    first = create_event()

    second = create_event()


    store.append(first)

    store.append(second)


    events = store.all_events()


    assert events[0] == first

    assert events[1] == second