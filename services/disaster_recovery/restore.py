class RestoreEngine:
    def restore(self, snapshot):
        snapshot.status = "RESTORED"
        return snapshot
