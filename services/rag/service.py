class RAGService:

    def __init__(

        self,

        embedding,

        store

    ):

        self.embedding = embedding

        self.store = store

    def ingest(self, document):

        vector = self.embedding.encode(
            document.content
        )

        self.store.save(

            document.document_id,

            vector

        )

    def query(self, document_id):

        return self.store.search(
            document_id
        )
