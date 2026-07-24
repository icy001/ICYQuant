from services.platform.knowledge import (
    KnowledgeEntity,
    KnowledgeGraph,
)


def test_graph():

    graph = KnowledgeGraph()

    graph.add_entity(
        KnowledgeEntity(
            "NVDA",
            "Stock",
            "NVIDIA",
        )
    )

    assert graph.entity(
        "NVDA"
    ).name == "NVIDIA"