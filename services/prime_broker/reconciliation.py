class BrokerReconciliationEngine:
    def reconcile(self, broker, internal):
        return {"matched": broker == internal}
