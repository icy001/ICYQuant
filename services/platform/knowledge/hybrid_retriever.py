"""
Hybrid retrieval engine.
"""


class HybridRetriever:

    def search(
        self,
        query,
        semantic_memory,
        vector_index,
    ):

        return {
            "query": query,
            "semantic": semantic_memory.retrieve(query),
            "vector_size": vector_index.count(),
        }