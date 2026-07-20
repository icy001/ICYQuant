from services.research import (
    KnowledgeRepository,
    ResearchKnowledge,
    ResearchNote,
    KnowledgeTag,
    KnowledgeSearch,
    KnowledgeService,
)


def test_save_knowledge():
    repository = KnowledgeRepository()

    knowledge = ResearchKnowledge(
        knowledge_id="doc-001",
        title="Momentum Strategy",
        category="Strategy",
    )

    repository.save(knowledge)

    assert repository.get("doc-001") == knowledge


def test_research_knowledge():
    knowledge = ResearchKnowledge(
        knowledge_id="doc-002",
        title="Factor Analysis",
        category="Research",
    )

    assert knowledge.knowledge_id == "doc-002"
    assert knowledge.category == "Research"


def test_research_note():
    note = ResearchNote(
        note_id="note-001",
        content="This strategy shows good performance in bear markets.",
    )

    assert note.note_id == "note-001"


def test_knowledge_tag():
    tag = KnowledgeTag(name="momentum")

    assert tag.name == "momentum"


def test_knowledge_search():
    search = KnowledgeSearch()

    results = search.search("strategy")

    assert isinstance(results, list)


def test_knowledge_service():
    repository = KnowledgeRepository()
    service = KnowledgeService(repository)

    knowledge = ResearchKnowledge(
        knowledge_id="doc-003",
        title="Alpha Factor",
        category="Factor",
    )

    result = service.publish(knowledge)

    assert result == knowledge
    assert repository.get("doc-003") == knowledge