from services.ai import ResearchNotebook


def test_research_notebook():

    notebook = ResearchNotebook()

    notebook.add(
        "Momentum Factor",
        "Test result",
    )

    assert len(
        notebook.list()
    ) == 1