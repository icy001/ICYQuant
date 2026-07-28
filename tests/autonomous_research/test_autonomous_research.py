from services.autonomous_research import (
    AutonomousResearchService,
    EvaluationReport,
    ExperimentLoop,
    ExperimentResult,
    ResearchEvaluator,
    ResearchGoal,
    ResearchPlanner,
    ResearchTask,
    ResearchWorkflow,
    TaskScheduler,
)


def test_autonomous_research():
    """Test the basic autonomous research pipeline."""
    planner = ResearchPlanner()
    service = AutonomousResearchService(planner)

    goal = ResearchGoal("G001", "Find AI semiconductor alpha")
    tasks = service.run(goal)

    assert len(tasks) == 3
    assert tasks == ["feature", "model", "backtest"]


def test_autonomous_research_full_pipeline():
    """Test the full pipeline including experiment and evaluation."""
    planner = ResearchPlanner()
    scheduler = TaskScheduler()
    experiment_loop = ExperimentLoop()
    evaluator = ResearchEvaluator(min_sharpe=0.3, good_sharpe=0.8)

    service = AutonomousResearchService(
        planner=planner,
        scheduler=scheduler,
        experiment_loop=experiment_loop,
        evaluator=evaluator,
    )

    goal = ResearchGoal("G002", "Build momentum strategy")
    result = service.run_full(goal)

    assert result["goal_id"] == "G002"
    assert result["task_count"] == 3
    assert len(result["task_results"]) == 3
    assert result["experiment"]["metrics"]["sharpe"] == 1.0
    assert result["evaluation"]["decision"] == "ACCEPT"
    assert result["evaluation"]["score"] == 1.0


def test_research_goal_lifecycle():
    """Test goal status transitions."""
    goal = ResearchGoal("G003", "Test goal")
    assert goal.status == "PENDING"

    goal.mark_planned()
    assert goal.status == "PLANNED"

    goal.mark_completed()
    assert goal.status == "COMPLETED"
    assert goal.completed_at is not None

    goal2 = ResearchGoal("G004", "Failed goal")
    goal2.mark_failed()
    assert goal2.status == "FAILED"


def test_research_task_lifecycle():
    """Test task status transitions."""
    task = ResearchTask("T001", "feature")
    assert task.status == "PENDING"

    task.mark_running()
    assert task.status == "RUNNING"
    assert task.started_at is not None

    task.mark_completed({"sharpe": 1.5})
    assert task.status == "COMPLETED"
    assert task.result == {"sharpe": 1.5}

    task2 = ResearchTask("T002", "backtest")
    task2.mark_failed("timeout")
    assert task2.status == "FAILED"
    assert task2.result == {"error": "timeout"}


def test_workflow_graph():
    """Test workflow DAG construction and traversal."""
    wf = ResearchWorkflow("WF001", "Test workflow")

    t1 = ResearchTask("T1", "data")
    t2 = ResearchTask("T2", "feature", dependencies=["T1"])
    t3 = ResearchTask("T3", "backtest", dependencies=["T2"])

    wf.add_task(t1)
    wf.add_task(t2)
    wf.add_task(t3)

    wf.add_edge("T1", "T2")
    wf.add_edge("T2", "T3")

    assert len(wf.tasks) == 3
    assert wf.get_next_tasks("T1") == ["T2"]
    assert wf.get_next_tasks("T2") == ["T3"]
    assert wf.get_next_tasks("T3") == []

    # Initially T1 should be ready (no deps)
    ready = wf.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "T1"


def test_workflow_completion():
    """Test workflow completion detection."""
    wf = ResearchWorkflow("WF002")
    t1 = ResearchTask("T1", "data")
    t2 = ResearchTask("T2", "backtest", dependencies=["T1"])

    wf.add_task(t1)
    wf.add_task(t2)
    wf.add_edge("T1", "T2")

    assert not wf.is_complete()

    t1.mark_completed({"ok": True})
    ready = wf.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "T2"

    t2.mark_completed({"ok": True})
    assert wf.is_complete()

    wf.mark_completed()
    assert wf.status == "COMPLETED"


def test_task_scheduler():
    """Test task scheduler execution."""
    scheduler = TaskScheduler()

    wf = ResearchWorkflow("WF003")
    t1 = ResearchTask("T1", "data")
    t2 = ResearchTask("T2", "feature", dependencies=["T1"])
    t3 = ResearchTask("T3", "backtest", dependencies=["T2"])

    wf.add_task(t1)
    wf.add_task(t2)
    wf.add_task(t3)

    results = scheduler.execute(wf)
    assert results == ["completed", "completed", "completed"]
    assert wf.status == "COMPLETED"
    assert all(t.status == "COMPLETED" for t in wf.tasks)


def test_task_scheduler_execute_ready():
    """Test scheduler executes only ready tasks."""
    scheduler = TaskScheduler()

    wf = ResearchWorkflow("WF004")
    t1 = ResearchTask("T1", "data")
    t2 = ResearchTask("T2", "feature", dependencies=["T1"])

    wf.add_task(t1)
    wf.add_task(t2)

    # First execution - only T1 is ready
    results = scheduler.execute_ready(wf)
    assert len(results) == 1
    assert results[0]["task_id"] == "T1"

    # Second execution - T2 is now ready
    results = scheduler.execute_ready(wf)
    assert len(results) == 1
    assert results[0]["task_id"] == "T2"
    assert wf.is_complete()


def test_experiment_loop():
    """Test experiment loop with multiple iterations."""
    loop = ExperimentLoop(max_iterations=5)

    result = loop.run("Momentum Strategy")
    assert result.status == "finished"
    assert result.strategy == "Momentum Strategy"
    assert "sharpe" in result.metrics
    assert len(loop.history) == 1


def test_experiment_loop_grid():
    """Test parameter grid search."""
    loop = ExperimentLoop(max_iterations=5)

    params_grid = [
        {"lookback": 20},
        {"lookback": 60},
        {"lookback": 120},
    ]

    results = loop.run_loop("Momentum", params_grid)
    assert len(results) == 3

    summary = loop.summary()
    assert summary["total_experiments"] == 3


def test_research_evaluator_accept():
    """Test evaluator accepts good results."""
    evaluator = ResearchEvaluator(min_sharpe=0.3, good_sharpe=0.8)

    result = ExperimentResult(
        iteration=1,
        strategy="test",
        metrics={"sharpe": 1.5, "ic": 0.08},
    )

    report = evaluator.evaluate(result)
    assert report.decision == "ACCEPT"
    assert report.score == 1.0


def test_research_evaluator_continue():
    """Test evaluator continues for marginal results."""
    evaluator = ResearchEvaluator(min_sharpe=0.3, good_sharpe=0.8)

    result = ExperimentResult(
        iteration=1,
        strategy="test",
        metrics={"sharpe": 0.5, "ic": 0.03},
    )

    report = evaluator.evaluate(result)
    assert report.decision == "CONTINUE"
    assert report.score == 0.5


def test_research_evaluator_discard():
    """Test evaluator discards poor results."""
    evaluator = ResearchEvaluator(min_sharpe=0.3, good_sharpe=0.8)

    result = ExperimentResult(
        iteration=1,
        strategy="test",
        metrics={"sharpe": 0.1, "ic": 0.005},
    )

    report = evaluator.evaluate(result)
    assert report.decision == "DISCARD"


def test_research_evaluator_best():
    """Test finding the best decision from multiple reports."""
    evaluator = ResearchEvaluator(min_sharpe=0.3, good_sharpe=0.8)

    results = [
        ExperimentResult(1, "s1", {"sharpe": 0.1, "ic": 0.02}),
        ExperimentResult(2, "s2", {"sharpe": 0.5, "ic": 0.04}),
        ExperimentResult(3, "s3", {"sharpe": 1.2, "ic": 0.06}),
    ]

    reports = evaluator.evaluate_all(results)
    assert len(reports) == 3
    assert reports[0].decision == "DISCARD"
    assert reports[1].decision == "CONTINUE"
    assert reports[2].decision == "ACCEPT"

    best = evaluator.best_decision(reports)
    assert best is not None
    assert best.decision == "ACCEPT"
    assert best.result.strategy == "s3"


def test_custom_task_planning():
    """Test custom task type planning."""
    planner = ResearchPlanner()
    service = AutonomousResearchService(planner)

    goal = ResearchGoal("G005", "Custom pipeline")
    result = service.run_with_custom_tasks(
        goal, ["data", "alpha", "signal", "backtest", "risk"]
    )

    assert result["goal_id"] == "G005"
    assert len(result["task_types"]) == 5
    assert result["evaluation_decision"] == "ACCEPT"


def test_workflow_summary():
    """Test workflow summary statistics."""
    wf = ResearchWorkflow("WF005", "Summary test")

    t1 = ResearchTask("T1", "data")
    t2 = ResearchTask("T2", "feature")
    t3 = ResearchTask("T3", "backtest")

    wf.add_task(t1)
    wf.add_task(t2)
    wf.add_task(t3)

    t1.mark_completed({"ok": True})
    t2.mark_failed("error")

    summary = wf.summary()
    assert summary["total_tasks"] == 3
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["pending"] == 1
