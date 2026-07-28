class FundReconciliationEngine:
    def reconcile(self, source, target):
        return {"matched": source == target}
