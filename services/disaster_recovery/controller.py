class FailoverController:
    def execute(self, failover):
        failover.status = "COMPLETED"
        return failover
