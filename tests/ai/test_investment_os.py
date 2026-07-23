from services.ai import InvestmentMemoryGraph


def test_memory_graph():

    graph = InvestmentMemoryGraph()

    graph.add_memory(
        "NVDA",
        "AI semiconductor leader"
    )

    assert graph.query(
        "NVDA"
    ) == "AI semiconductor leader"