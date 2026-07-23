"""
Exchange connector.
"""


class ExchangeConnector:

    def connect(self):
        return {
            "exchange":
                "connected"
        }

    def disconnect(self):
        return {
            "exchange":
                "closed"
        }