class WorkflowRepository:

    def __init__(self):
        self.instances = {}
        self.snapshots = {}

    def save_instance(self, instance):
        self.instances[instance.workflow_id] = instance

    def save_snapshot(self, snapshot):
        self.snapshots[snapshot.workflow_id] = snapshot

    def get_snapshot(self, workflow_id):
        return self.snapshots.get(workflow_id)
