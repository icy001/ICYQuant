class DisasterRecoveryService:
    def __init__(self, backup_manager, restore_engine, controller):
        self.backup_manager = backup_manager
        self.restore_engine = restore_engine
        self.controller = controller

    def backup(self, snapshot):
        return self.backup_manager.create(snapshot)

    def restore(self, snapshot):
        return self.restore_engine.restore(snapshot)

    def failover(self, failover):
        return self.controller.execute(failover)
