from services.ai import (
    WorkflowDAG,
    WorkflowNode,
    WorkflowEdge,
)


def test_workflow_dependency():

    dag = WorkflowDAG()

    dag.add_node(
        WorkflowNode(
            "A",
            "research",
            "agent1",
        )
    )

    dag.add_node(
        WorkflowNode(
            "B",
            "analysis",
            "agent2",
        )
    )

    dag.add_edge(
        WorkflowEdge(
            "A",
            "B",
        )
    )

    assert dag.dependencies(
        "B"
    ) == ["A"]