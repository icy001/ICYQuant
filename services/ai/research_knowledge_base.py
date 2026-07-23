"""
AI research knowledge base.
"""


class ResearchKnowledgeBase:

    def __init__(self):

        self.documents = []

    def store(
        self,
        document,
    ):

        self.documents.append(
            document
        )

    def search(
        self,
        keyword,
    ):

        return [
            doc
            for doc in self.documents
            if keyword in str(doc)
        ]