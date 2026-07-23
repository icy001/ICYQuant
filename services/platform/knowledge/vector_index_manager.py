"""
Vector index manager.
"""


class VectorIndexManager:

    def __init__(self):

        self.index = {}

    def upsert(
        self,
        doc_id,
        embedding,
    ):

        self.index[doc_id] = embedding

    def count(self):

        return len(self.index)