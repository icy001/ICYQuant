class PrimeBrokerAdapter:
    def connect(self, broker):
        return {"broker": broker, "status": "connected"}
