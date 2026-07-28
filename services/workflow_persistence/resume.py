class ResumeEngine:

    def resume(self, workflow):
        workflow.state = "RUNNING"

        return workflow
