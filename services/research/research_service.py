"""
Research service.
"""


class ResearchService:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def create_project(
        self,
        project,
    ):

        self.repository.save(
            project
        )

        return project