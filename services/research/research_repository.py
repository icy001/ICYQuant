"""
Research repository.
"""


class ResearchRepository:

    def __init__(self):

        self.projects = {}

    def save(
        self,
        project,
    ):

        self.projects[
            project.project_id
        ] = project

    def get(
        self,
        project_id,
    ):

        return self.projects.get(
            project_id
        )