"""
AI research notebook.
"""


class ResearchNotebook:

    def __init__(self):

        self.entries = []

    def add(
        self,
        title,
        content,
    ):

        self.entries.append(
            {
                "title": title,
                "content": content,
            }
        )

    def list(self):

        return self.entries