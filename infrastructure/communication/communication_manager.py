"""
Central communication manager.
"""


class CommunicationManager:

    def __init__(
        self,
        client,
    ):
        self.client = client

    def send(
        self,
        request,
    ):
        return self.client.call(
            request.service,
            request
        )