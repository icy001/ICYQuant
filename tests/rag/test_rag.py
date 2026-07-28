from services.rag import *


def test_rag():

    store = VectorStore()

    embedding = EmbeddingService()

    service = RAGService(

        embedding,

        store

    )

    doc = Document(

        "DOC001",

        "NVDA Research",

        "Momentum factor analysis"

    )

    service.ingest(doc)

    result = service.query(
        "DOC001"
    )

    assert result == [

        len(
            "Momentum factor analysis"
        )

    ]
