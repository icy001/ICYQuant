class DeadLetterQueue:
    def __init__(self):
        self.failed = []

    def add(self, message):
        self.failed.append(message)
