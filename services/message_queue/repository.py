class MessageRepository:
    def __init__(self):
        self.messages = []

    def append(self, message):
        self.messages.append(message)

    def get_all(self):
        return self.messages
