class ReplayEngine:
    def replay(
        self,
        events: list,
    ) -> float:
        quantity = 0.0

        for event in events:
            if event["type"] == "BUY":
                quantity += event["quantity"]
            elif event["type"] == "SELL":
                quantity -= event["quantity"]

        return quantity
