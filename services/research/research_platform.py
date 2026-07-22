"""
Unified research platform.
"""


class UnifiedResearchPlatform:

    def __init__(
        self,
        bootstrap=None,
        workflow_service=None,
        container=None,
    ):

        self.bootstrap = bootstrap
        self.workflow_service = workflow_service
        self.container = container

    def start(
        self,
        workflow=None,
        notebook=None,
        dependencies=None,
        modules=None,
    ):

        if self.container is not None:
            return True

        if self.bootstrap and self.workflow_service:
            self.bootstrap.initialize(
                dependencies,
                modules,
            )
            return self.workflow_service.execute(
                workflow,
                notebook,
            )

        return True