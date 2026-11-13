"""Tests for read-only Statistics Analysis snapshot imports."""

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from samialbion.statistics_analysis_import import load_statistics_analysis_snapshot


def dotnet_ticks(date: datetime) -> int:
    utc = date.astimezone(timezone.utc)
    epoch = datetime(1, 1, 1, tzinfo=timezone.utc)
    delta = utc - epoch
    return (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10


class StatisticsAnalysisImportTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.path = Path(self.folder.name) / "Gathering.json"
        self.ticks = dotnet_ticks(datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc))

    def tearDown(self):
        self.folder.cleanup()

    def _write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_aggregate_realistic_pascal_case_snapshot_and_keep_source_unchanged(self):
        records = [
            dict(SessionId="my-session", CharacterName="Sami",
                 Timestamp=self.ticks, UniqueItemName="T6_ORE",
                 GainedStandardAmount=3, GainedBonusAmount=2,
                 GainedPremiumBonusAmount=1, MiningProcesses=1),
            dict(SessionId="my-session", CharacterName="Sami",
                 Timestamp=self.ticks + 600_000_000, UniqueItemName="T6_ORE",
                 GainedStandardAmount=4, GainedBonusAmount=1,
                 GainedPremiumBonusAmount=0, MiningProcesses=2),
            dict(SessionId="another", CharacterName="Sami",
                 Timestamp=self.ticks, UniqueItemName="T7_FIBER",
                 GainedStandardAmount=2, MiningProcesses=1)
        ]
        self._write(records)
        before = self.path.read_bytes()
        sessions = load_statistics_analysis_snapshot(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(sessions), 2)
        first = next(x for x in sessions if x.session_id == "my-session")
        self.assertEqual(first.total_resources, 11)
        self.assertEqual(first.resources[0].standard, 7)
        self.assertEqual(first.resources[0].gathering_bonus, 3)
        self.assertEqual(first.resources[0].premium_bonus, 1)
        self.assertEqual(first.event_count, 3)
        self.assertEqual(first.observed_span_seconds, 60)

    def test_refresh_replaces_snapshot_not_double_counts(self):
        self._write([dict(SessionId="s1", CharacterName="Sami",
                          Timestamp=self.ticks, UniqueItemName="T6_ORE",
                          GainedStandardAmount=3)])
        self.assertEqual(load_statistics_analysis_snapshot(self.path)[0].total_resources, 3)
        self.assertEqual(load_statistics_analysis_snapshot(self.path)[0].total_resources, 3)
        self._write([dict(SessionId="s1", CharacterName="Sami",
                          Timestamp=self.ticks, UniqueItemName="T6_ORE",
                          GainedStandardAmount=8)])
        self.assertEqual(load_statistics_analysis_snapshot(self.path)[0].total_resources, 8)

    def test_invalid_file_is_rejected_without_writing(self):
        with self.assertRaises(ValueError):
            load_statistics_analysis_snapshot(self.path.parent / "Other.json")
        self.path.write_text('{"not":"an array"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_statistics_analysis_snapshot(self.path)

    def test_old_blank_sessions_stay_separate_by_character(self):
        self._write([
            dict(SessionId="00000000-0000-0000-0000-000000000000",
                 CharacterName="Sami", Timestamp=self.ticks,
                 UniqueItemName="T5_WOOD", GainedStandardAmount=1),
            dict(SessionId="00000000-0000-0000-0000-000000000000",
                 CharacterName="Amie", Timestamp=self.ticks,
                 UniqueItemName="T5_WOOD", GainedStandardAmount=2),
        ])
        sessions = load_statistics_analysis_snapshot(self.path)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sorted(x.total_resources for x in sessions), [1, 2])


if __name__ == "__main__":
    unittest.main()
