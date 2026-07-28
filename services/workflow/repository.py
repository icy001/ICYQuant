class WorkflowRepository:
    def __init__(self):
        self.workflows = {}

    def save(self, workflow):
        self.workflows[workflow.instance_id] = workflow

    def get(self, instance_id):
        return self.workflows.get(instance_id)
