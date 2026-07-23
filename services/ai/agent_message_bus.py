"""
Agent message bus.
"""


class AgentMessageBus:

    def __init__(self):

        self.messages = []

    def publish(self, message):

        self.messages.append(message)

    def consume(self):

        messages = self.messages[:]

        self.messages.clear()

        return messages