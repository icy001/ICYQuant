"""
Recovery history.
"""


class RecoveryHistory:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def records(self):

        return self.repository.list_all()