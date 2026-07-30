class MessageQueueService:
    def __init__(self, producer, repository, consumer_manager):
        self.producer = producer
        self.repository = repository
        self.consumer_manager = consumer_manager

    def publish(self, message):
        return self.producer.publish(message)

    def consume(self, topic):
        return self.consumer_manager.consume(self.repository.get_all(), topic)
