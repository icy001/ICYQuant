class Producer:
    def __init__(self, repository):
        self.repository = repository

    def publish(self, message):
        self.repository.append(message)
        return message
