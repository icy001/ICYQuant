import pytest

from services.research import (
    ResearchWorkflow,
    WorkflowOrchestrator,
    WorkflowTask,
    WorkflowScheduler,
    DependencyResolver,
    WorkflowService,
)


@pytest.mark.asyncio
async def test_workflow_execution():
    workflow = ResearchWorkflow(
        workflow_id="wf-001",
        name="Daily Research",
        tasks=["backtest", "report"],
    )

    orchestrator = WorkflowOrchestrator()

    result = await orchestrator.execute(workflow)

    assert result["status"] == "COMPLETED"


def test_research_workflow():
    workflow = ResearchWorkflow(
        workflow_id="wf-002",
        name="Optimization Pipeline",
        tasks=["parameter_search", "backtest", "analysis"],
    )

    assert workflow.workflow_id == "wf-002"
    assert len(workflow.tasks) == 3


def test_workflow_task():
    task = WorkflowTask(
        task_id="task-001",
        name="backtest",
        status="RUNNING",
    )

    assert task.task_id == "task-001"
    assert task.status == "RUNNING"


def test_workflow_scheduler():
    scheduler = WorkflowScheduler()

    workflow = ResearchWorkflow(
        workflow_id="wf-003",
        name="Scheduler Test",
        tasks=["task1", "task2"],
    )

    tasks = scheduler.schedule(workflow)

    assert len(tasks) == 2


def test_dependency_resolver():
    resolver = DependencyResolver()

    tasks = ["task1", "task2", "task3"]
    resolved = resolver.resolve(tasks)

    assert resolved == tasks


@pytest.mark.asyncio
async def test_workflow_service():
    orchestrator = WorkflowOrchestrator()
    service = WorkflowService(orchestrator)

    workflow = ResearchWorkflow(
        workflow_id="wf-004",
        name="Service Test",
        tasks=["backtest", "report"],
    )

    result = await service.run(workflow)

    assert result["workflow"] == "wf-004"