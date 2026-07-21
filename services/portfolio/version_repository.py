"""
Version repository.
"""


class VersionRepository:
    def __init__(self):
        self.versions = []

    def save(
        self,
        version,
    ):
        self.versions.append(version)

    def list_all(self):
        return self.versions