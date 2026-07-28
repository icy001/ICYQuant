class WorkflowScheduler:
    def schedule(self, workflow):
        workflow.state = "RUNNING"
        return workflow
