"""
Access workflow service.
"""


class AccessWorkflowService:
    def __init__(
        self,
        workflow,
    ):
        self.workflow = workflow

    def submit(
        self,
        request,
    ):
        return request

    def approve(
        self,
        request,
    ):
        return self.workflow.approve(request)