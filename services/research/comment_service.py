"""
Comment service.
"""


class CommentService:

    def __init__(self):

        self._comments = []

    def add(
        self,
        comment,
    ):

        self._comments.append(
            comment
        )

    def list_all(self):

        return self._comments