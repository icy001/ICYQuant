"""
Broker API adapter.
"""


class BrokerAdapter:

    def submit_order(
        self,
        order,
    ):
        return {
            "order":
                order,
            "status":
                "submitted"
        }