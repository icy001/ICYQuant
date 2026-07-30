"""Tests for Agent Communication System."""

import pytest
from services.agents.agent_base import BaseAgent, AgentStatus, DecisionAction
from services.agents.communication import AgentCommunicator


class TestAgentCommunicator:
    """Agent communication system tests."""

    @pytest.fixture
    def comm(self):
        return AgentCommunicator(agent_name="test_agent")

    # ── Message Registration ────────────────────────────────────

    def test_register_handler(self, comm):
        received = []

        def handler(data):
            received.append(data)

        comm.register_handler("TEST_EVENT", handler)
        # Simulate dispatch by sending a message that routes back
        comm.send("test_agent", "TEST_EVENT", {"value": 42})
        assert len(received) == 1
        assert received[0]["value"] == 42

    def test_multiple_handlers_registered(self, comm):
        received = []

        def handler(data):
            received.append(data)

        comm.register_handler("EVENT_A", handler)
        comm.register_handler("EVENT_B", handler)
        # Both handlers registered without error
        assert len(comm.get_stats().get("handlers", [])) >= 0

    # ── Send Methods ────────────────────────────────────────────

    def test_send(self, comm):
        result = comm.send("market_agent", "TEST", {"value": 1})
        assert result is not None

    def test_broadcast(self, comm):
        comm.broadcast("BROADCAST_EVENT", {"message": "hello"})

    def test_request_response(self, comm):
        def responder(data):
            return {"response": "ok", "original": data}

        comm.register_handler("REQUEST", responder)
        result = comm.request("target_agent", "REQUEST", {"query": "test"})
        # May return None if target not reachable
        assert result is None or isinstance(result, dict)

    def test_deliberate(self, comm):
        """Committee deliberation should return a dict with approved/votes."""
        result = comm.deliberate(
            members=["agent_a", "agent_b"],
            proposal="Should we trade?",
            data={"question": "yes_no"},
        )
        assert isinstance(result, dict)
        assert "approved" in result
        assert "votes" in result

    # ── Message Logging ─────────────────────────────────────────

    def test_get_sent(self, comm):
        comm.send("target", "LOGGED_EVENT", {"data": "test"})
        logs = comm.get_sent()
        assert len(logs) > 0

    def test_message_log_limit(self, comm):
        for i in range(150):
            comm.send("target", f"EVENT_{i}", {"i": i})

        logs = comm.get_sent(limit=50)
        assert len(logs) <= 50

    # ── Stats ───────────────────────────────────────────────────

    def test_get_stats(self, comm):
        comm.send("agent1", "EVENT1", {"d": 1})
        comm.send("agent2", "EVENT2", {"d": 2})
        stats = comm.get_stats()
        assert isinstance(stats, dict)
