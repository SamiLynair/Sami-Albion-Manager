"""Offline tests: no Albion client, network access, or game process required."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from samialbion.gathering_sessions import GatheringStore


START = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)


class GatheringSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.db_path = Path(self.temporary.name) / "sessions.db"
        self.store = GatheringStore(self.db_path)
        self.session = self.store.start_session("TestCharacter", at=START)

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_standard_bonus_and_premium_are_not_double_counted(self):
        self.store.add_event(self.session, "T6_ORE", 3, gathering_bonus=2, premium_bonus=1,
                             occurred_at=START + timedelta(minutes=1))
        self.store.add_event(self.session, "T6_ORE", 2,
                             occurred_at=START + timedelta(minutes=2))
        self.store.add_event(self.session, "T7_FIBER", 5,
                             occurred_at=START + timedelta(minutes=3))
        summary = self.store.summary(self.session, unit_prices={"T6_ORE": 100, "T7_FIBER": 200},
                                     now=START + timedelta(hours=2))
        self.assertEqual(summary.total_resources, 13)
        self.assertEqual(summary.event_count, 3)
        self.assertEqual(summary.resources[0].total, 8)
        self.assertEqual(summary.resources[0].gathering_bonus, 2)
        self.assertEqual(summary.resources[0].premium_bonus, 1)
        self.assertEqual(summary.known_silver_value, 1800)
        self.assertEqual(summary.resources_per_hour, 6.5)
        self.assertEqual(summary.estimated_silver_per_hour, 900)

    def test_missing_prices_are_reported_not_silently_treated_as_zero(self):
        self.store.add_event(self.session, "T8_WOOD", 1, occurred_at=START)
        summary = self.store.summary(self.session, now=START + timedelta(hours=1))
        self.assertEqual(summary.known_silver_value, 0)
        self.assertEqual(summary.unpriced_resource_ids, ("T8_WOOD",))
        self.assertIsNone(summary.estimated_silver_per_hour)

    def test_duplicate_event_is_idempotent_and_conflict_rejected(self):
        self.assertTrue(self.store.add_event(self.session, "T6_ORE", 3,
                       event_id="source-1", occurred_at=START))
        self.assertFalse(self.store.add_event(self.session, "T6_ORE", 3,
                        event_id="source-1", occurred_at=START))
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", 9,
                                 event_id="source-1", occurred_at=START)
        self.assertEqual(self.store.summary(self.session, now=START).total_resources, 3)

    def test_restart_keeps_session_and_events(self):
        self.store.add_event(self.session, "T5_HIDE", 4, occurred_at=START)
        self.store.close()
        self.store = GatheringStore(self.db_path)
        self.assertEqual(self.store.summary(self.session, now=START).total_resources, 4)
        self.assertEqual(len(self.store.list_sessions(character="TestCharacter")), 1)

    def test_closed_session_rejects_new_events(self):
        self.store.end_session(self.session, at=START + timedelta(hours=1))
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", 1,
                                 occurred_at=START + timedelta(hours=1))
        self.assertEqual(self.store.summary(self.session).duration_seconds, 3600)

    def test_invalid_amounts_timestamps_and_names(self):
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", -1, occurred_at=START)
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", 0, occurred_at=START)
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", True, occurred_at=START)
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", 1,
                                 occurred_at=START - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            self.store.start_session("  ")
        with self.assertRaises(ValueError):
            self.store.end_session(self.session, at=START - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            self.store.add_event(self.session, "T6_ORE", 1,
                                 occurred_at=datetime(2026, 11, 13))


if __name__ == "__main__":
    unittest.main()
