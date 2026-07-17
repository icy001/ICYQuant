from services.data.pipeline import (
    PipelineTask,
    PipelineDAG,
    DependencyResolver,
    RetryPolicy,
    ExecutionRecord,
    PipelineScheduler,
    PipelineService,
)


def test_pipeline_dag():
    dag = PipelineDAG()

    task = PipelineTask(task_id="feature", name="Feature Generate")

    dag.add_task(task)

    assert dag.tasks["feature"] == task


def test_pipeline_task():
    task = PipelineTask(task_id="calculate_factor", name="Calculate Factor")

    assert task.task_id == "calculate_factor"
    assert task.name == "Calculate Factor"
    assert task.status == "PENDING"


def test_pipeline_dag_dependency():
    dag = PipelineDAG()

    dag.add_task(PipelineTask(task_id="ingest", name="Ingest"))
    dag.add_task(PipelineTask(task_id="feature", name="Feature"))

    dag.add_dependency("ingest", "feature")

    assert "ingest" in dag.edges
    assert "feature" in dag.edges["ingest"]


def test_dependency_resolver():
    resolver = DependencyResolver()

    completed = {"task_a": ["dep1"], "task_b": []}
    result = resolver.ready("task_b", completed)

    assert result is True


def test_retry_policy():
    policy = RetryPolicy(max_retry=3)

    assert policy.max_retry == 3


def test_retry_policy_default():
    policy = RetryPolicy()

    assert policy.max_retry == 3


def test_execution_record():
    record = ExecutionRecord(
        pipeline_id="pipeline_001",
        status="RUNNING",
        started_at="2026-07-17T09:00:00",
    )

    assert record.pipeline_id == "pipeline_001"
    assert record.status == "RUNNING"


def test_pipeline_scheduler():
    scheduler = PipelineScheduler()
    dag = PipelineDAG()

    dag.add_task(PipelineTask(task_id="task1", name="Task 1"))
    dag.add_task(PipelineTask(task_id="task2", name="Task 2"))

    tasks = scheduler.schedule(dag)

    assert len(tasks) == 2


def test_pipeline_service():
    scheduler = PipelineScheduler()
    service = PipelineService(scheduler)
    dag = PipelineDAG()

    dag.add_task(PipelineTask(task_id="task1", name="Task 1"))

    tasks = service.run(dag)

    assert len(tasks) == 1