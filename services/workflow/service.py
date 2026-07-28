from .scheduler import WorkflowScheduler


class WorkflowService:
    def __init__(self, repository):
        self.repository = repository
        self.scheduler = WorkflowScheduler()

    def start(self, workflow):
        workflow = self.scheduler.schedule(workflow)
        self.repository.save(workflow)
        return workflow
