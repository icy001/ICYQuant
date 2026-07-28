class ConsumerManager:

    def consume(
        self,
        messages,
        topic
    ):

        return [
            m
            for m in messages
            if m.topic == topic
        ]
