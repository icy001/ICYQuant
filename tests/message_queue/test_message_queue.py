from services.message_queue import *


def test_message_queue():

    repository = MessageRepository()

    service = MessageQueueService(
        Producer(repository),
        repository,
        ConsumerManager()
    )

    service.publish(
        Message(
            "MSG001",
            "ORDER_CREATED",
            {
                "order_id": "10001"
            },
            "NEW"
        )
    )

    result = service.consume(
        "ORDER_CREATED"
    )

    assert len(result) == 1
