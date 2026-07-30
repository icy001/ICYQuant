"""
Tests for ICYQuant Workflow Engine and Event Router.
"""

import pytest
import time

from platform.workflow_engine import WorkflowEngine, WorkflowStatus
from platform.event_router import EventRouter, EventPriority


class TestWorkflowEngine:
    """Test workflow creation, execution, and management."""

    def test_create_workflow(self):
        engine = WorkflowEngine()
        wf = engine.create_workflow(
            name="Test Workflow",
            steps=[
                {"name": "step1", "action": "test"},
                {"name": "step2", "action": "test"},
            ],
        )
        assert wf.name == "Test Workflow"
        assert wf.status == WorkflowStatus.PENDING
        assert len(wf.steps) == 2

    def test_start_workflow(self):
        engine = WorkflowEngine()
        wf = engine.create_workflow(
            name="Test",
            steps=[{"name": "step1", "action": "test"}],
        )
        success = engine.start_workflow(wf.workflow_id)
        assert success is True
        wf = engine.get_workflow(wf.workflow_id)
        assert wf.status == WorkflowStatus.COMPLETED

    def test_workflow_with_handler(self):
        engine = WorkflowEngine()
        results = []

        def step_handler(params):
            results.append(params)
            return {"status": "ok"}

        wf = engine.create_workflow(
            name="Test",
            steps=[{
                "name": "step1",
                "action": "test",
                "parameters": {"data": "hello"},
                "handler": step_handler,
            }],
        )
        engine.start_workflow(wf.workflow_id)
        assert len(results) == 1
        assert results[0]["data"] == "hello"

    def test_workflow_with_approval(self):
        engine = WorkflowEngine()
        wf = engine.create_workflow(
            name="Approval Test",
            steps=[{
                "name": "step1",
                "action": "test",
                "requires_approval": True,
            }],
        )
        engine.start_workflow(wf.workflow_id)
        wf = engine.get_workflow(wf.workflow_id)
        assert wf.status == WorkflowStatus.APPROVAL_REQUIRED

    def test_approve_step(self):
        engine = WorkflowEngine()
        wf = engine.create_workflow(
            name="Approval",
            steps=[{
                "name": "step1",
                "action": "test",
                "requires_approval": True,
            }],
        )
        engine.start_workflow(wf.workflow_id)
        success = engine.approve_step(wf.workflow_id, "admin")
        assert success is True
        wf = engine.get_workflow(wf.workflow_id)
        assert wf.status == WorkflowStatus.COMPLETED

    def test_cancel_workflow(self):
        engine = WorkflowEngine()
        wf = engine.create_workflow(
            name="Cancel Test",
            steps=[{"name": "step1", "action": "test"}],
        )
        engine.start_workflow(wf.workflow_id)
        assert engine.cancel_workflow(wf.workflow_id) is True

    def test_workflow_with_retries(self):
        engine = WorkflowEngine()
        call_count = [0]

        def flaky_handler(params):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Temporary failure")
            return {"status": "ok"}

        wf = engine.create_workflow(
            name="Retry Test",
            steps=[{
                "name": "step1",
                "action": "test",
                "handler": flaky_handler,
                "retries": 3,
            }],
        )
        engine.start_workflow(wf.workflow_id)
        assert call_count[0] == 3
        wf = engine.get_workflow(wf.workflow_id)
        assert wf.status == WorkflowStatus.COMPLETED

    def test_list_active(self):
        engine = WorkflowEngine()
        engine.create_workflow("wf1", [{"name": "s1", "action": "test"}])
        active = engine.list_active()
        assert len(active) == 1

    def test_register_template(self):
        engine = WorkflowEngine()
        engine.register_template("test_template", [
            {"name": "s1", "action": "test"},
        ])
        templates = engine.list_templates()
        assert "test_template" in templates

    def test_get_status(self):
        engine = WorkflowEngine()
        engine.create_workflow("test", [{"name": "s1", "action": "test"}])
        status = engine.get_status()
        assert "totalActive" in status


class TestEventRouter:
    """Test event routing and pub/sub."""

    def test_subscribe_and_publish(self):
        router = EventRouter()
        received = []
        router.subscribe("sub1", "test.topic", lambda e: received.append(e))
        router.publish("test.topic", payload={"data": "hello"})
        assert len(received) == 1
        assert received[0].payload["data"] == "hello"

    def test_multiple_subscribers(self):
        router = EventRouter()
        received1 = []
        received2 = []
        router.subscribe("sub1", "test.topic", lambda e: received1.append(e))
        router.subscribe("sub2", "test.topic", lambda e: received2.append(e))
        router.publish("test.topic", payload={"data": "hello"})
        assert len(received1) == 1
        assert len(received2) == 1

    def test_filter(self):
        router = EventRouter()
        received = []
        router.subscribe(
            "sub1", "test.topic",
            lambda e: received.append(e),
            filter_fn=lambda p: p.get("value", 0) > 10,
        )
        router.publish("test.topic", payload={"value": 5})
        router.publish("test.topic", payload={"value": 15})
        assert len(received) == 1

    def test_priority_filter(self):
        router = EventRouter()
        received = []
        router.subscribe(
            "sub1", "test.topic",
            lambda e: received.append(e),
            min_priority=EventPriority.HIGH,
        )
        router.publish("test.topic", payload={}, priority=EventPriority.LOW)
        router.publish("test.topic", payload={}, priority=EventPriority.CRITICAL)
        assert len(received) == 1

    def test_wildcard_subscription(self):
        router = EventRouter()
        received = []
        router.subscribe("sub1", "*", lambda e: received.append(e))
        router.publish("topic.a", payload={})
        router.publish("topic.b", payload={})
        assert len(received) == 2

    def test_unsubscribe(self):
        router = EventRouter()
        received = []
        router.subscribe("sub1", "test.topic", lambda e: received.append(e))
        router.unsubscribe("sub1", "test.topic")
        router.publish("test.topic", payload={})
        assert len(received) == 0

    def test_broadcast(self):
        router = EventRouter()
        received = []
        router.subscribe("sub1", "test.topic", lambda e: received.append(e))
        router.broadcast("test.topic", payload={"data": "broadcast"})
        assert len(received) == 1

    def test_get_topics(self):
        router = EventRouter()
        router.subscribe("sub1", "topic.a", lambda e: None)
        router.subscribe("sub2", "topic.b", lambda e: None)
        topics = router.get_topics()
        assert "topic.a" in topics
        assert "topic.b" in topics

    def test_get_stats(self):
        router = EventRouter()
        router.subscribe("sub1", "test", lambda e: None)
        router.publish("test", payload={})
        stats = router.get_stats()
        assert stats["published"] == 1
        assert stats["delivered"] == 1
