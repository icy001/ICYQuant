class OrderSimulator:
    def execute(self, order):
        return {
            "order_id": order,
            "status": "FILLED"
        }