"""
Order simulator.
"""


class OrderSimulator:
    async def submit(
        self,
        order,
    ):
        return {
            "accepted": True,
            "order": order,
        }