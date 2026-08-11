"""Tests for DeadLetterManager — dead-letter queue lifecycle."""

import unittest

from services.oms.dead_letter.dead_letter_manager import DeadLetterManager
from services.oms.dead_letter.dead_letter_entry import DeadLetterStatus


class TestDeadLetterManager(unittest.TestCase):

    def setUp(self):
        self.manager = DeadLetterManager()

    def test_add_entry(self):
        entry = self.manager.add(
            message_id="MSG-001",
            order_id="ORD-001",
            message_type="EXECUTION_REPORT",
            failure_code="EXECUTION_ID_CONFLICT",
            failure_reason="Same ID, different payload",
            payload={"execution_id": "EXEC-1", "qty": 300},
        )
        self.assertEqual(entry.status, DeadLetterStatus.OPEN)
        self.assertEqual(self.manager.total_count, 1)

    def test_add_duplicate_updates_existing(self):
        self.manager.add(
            "MSG-001", "ORD-001", "EXECUTION_REPORT",
            "EXECUTION_ID_CONFLICT", "conflict",
        )
        self.manager.add(
            "MSG-001", "ORD-001", "EXECUTION_REPORT",
            "EXECUTION_ID_CONFLICT", "conflict",
        )
        self.assertEqual(self.manager.total_count, 1)

    def test_resolve(self):
        self.manager.add(
            "MSG-001", "ORD-001", "EXECUTION_REPORT",
            "CONFLICT", "conflict",
        )
        entry = self.manager.resolve("MSG-001", "admin", "Manually verified")
        # Resolve uses dead_letter_id, not message_id
        # Let's get it by message_id first
        entries = self.manager.get_entries_for_order("ORD-001")
        entry = self.manager.resolve(entries[0].dead_letter_id, "admin", "verified")
        self.assertEqual(entry.status, DeadLetterStatus.RESOLVED)

    def test_ignore_requires_actor_and_reason(self):
        self.manager.add(
            "MSG-001", "ORD-001", "EXECUTION_REPORT",
            "CONFLICT", "conflict",
        )
        entries = self.manager.get_entries_for_order("ORD-001")
        with self.assertRaises(ValueError):
            self.manager.ignore(entries[0].dead_letter_id, "", "")
        entry = self.manager.ignore(
            entries[0].dead_letter_id, "admin", "Duplicate, safe to ignore",
        )
        self.assertEqual(entry.status, DeadLetterStatus.IGNORED)

    def test_escalate(self):
        self.manager.add(
            "MSG-001", "ORD-001", "EXECUTION_REPORT",
            "CONFLICT", "conflict",
        )
        entries = self.manager.get_entries_for_order("ORD-001")
        entry = self.manager.escalate(entries[0].dead_letter_id)
        self.assertEqual(entry.status, DeadLetterStatus.ESCALATED)

    def test_get_open_entries(self):
        self.manager.add("MSG-1", "ORD-1", "ACK", "FAIL", "r")
        self.manager.add("MSG-2", "ORD-2", "ACK", "FAIL", "r")
        self.assertEqual(len(self.manager.get_open_entries()), 2)

    def test_open_count(self):
        self.manager.add("MSG-1", "ORD-1", "ACK", "FAIL", "r")
        self.assertEqual(self.manager.open_count, 1)


if __name__ == '__main__':
    unittest.main()
