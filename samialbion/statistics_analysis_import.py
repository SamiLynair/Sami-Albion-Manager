"""Read-only importer for Statistics Analysis gathering snapshots.

Reads only the JSON file *written by Statistics Analysis itself*. No socket
creation, packet sniffing, process access or Albion protocol processing.
This is a third-party file integration, not a standalone game tracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from .gathering_sessions import GatheredResource


MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
DOTNET_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


def _timestamp(ticks: int) -> datetime:
    if type(ticks) is not int or ticks <= 0:
        raise ValueError("Invalid Statistics Analysis timestamp")
    try:
        return DOTNET_EPOCH + timedelta(microseconds=ticks // 10)
    except (OverflowError, ValueError) as error:
        raise ValueError("Invalid Statistics Analysis timestamp") from error


def _amount(record: dict, key: str) -> int:
    value = record.get(key, 0)
    if type(value) is not int or not 0 <= value <= 1_000_000_000:
        raise ValueError(f"Invalid {key} gathering amount")
    return value


@dataclass(frozen=True)
class ImportedGatheringSession:
    """Statistics Analysis session snapshot, not an event-level live stream."""

    session_id: str
    character: str
    first_record_at: datetime
    last_record_at: datetime
    event_count: int
    resources: tuple[GatheredResource, ...]

    @property
    def total_resources(self) -> int:
        return sum(item.total for item in self.resources)

    @property
    def observed_span_seconds(self) -> float:
        """Time between *first-record timestamps*, not true playtime."""
        return max(0.0, (self.last_record_at - self.first_record_at).total_seconds())


def load_statistics_analysis_snapshot(path: str | Path) -> tuple[ImportedGatheringSession, ...]:
    """Load a Statistics Analysis Gathering.json snapshot without modifying it.

    The source format is an array of GatheredDto records (PascalCase fields).
    Entries for one resource object can accumulate multiple harvest actions.
    Their timestamp is the time that resource entry began, so the last
    timestamp is NOT a reliable session end time.
    """
    file_path = Path(path)
    if file_path.name.lower() != "gathering.json":
        raise ValueError("Select the Statistics Analysis Gathering.json file")
    if file_path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("Statistics Analysis gathering file is too large")
    with file_path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Statistics Analysis Gathering.json must contain a list")

    sessions: dict[tuple[str, str], dict] = {}
    for record in data:
        if not isinstance(record, dict):
            continue
        session_id = str(record.get("SessionId") or "").strip()
        character = record.get("CharacterName")
        item_id = record.get("UniqueItemName")
        if not isinstance(character, str) or not isinstance(item_id, str):
            continue
        character, item_id = character.strip(), item_id.strip()
        if not character or not item_id or len(item_id) > 150:
            continue
        timestamp = _timestamp(record.get("Timestamp"))
        standard = _amount(record, "GainedStandardAmount")
        bonus = _amount(record, "GainedBonusAmount")
        premium = _amount(record, "GainedPremiumBonusAmount")
        if not standard + bonus + premium:
            continue
        actions = _amount(record, "MiningProcesses")
        # Legacy SA records may not contain a valid session id.
        key = (session_id or "legacy", character)
        current = sessions.setdefault(key, {
            "first": timestamp, "last": timestamp, "actions": 0, "resources": {}
        })
        current["first"] = min(current["first"], timestamp)
        current["last"] = max(current["last"], timestamp)
        current["actions"] += actions
        amounts = current["resources"].setdefault(item_id, [0, 0, 0])
        amounts[0] += standard
        amounts[1] += bonus
        amounts[2] += premium

    result = []
    for (session_id, character), values in sessions.items():
        resources = tuple(
            GatheredResource(item_id, *amounts)
            for item_id, amounts in sorted(values["resources"].items())
        )
        result.append(ImportedGatheringSession(
            session_id, character, values["first"], values["last"],
            values["actions"], resources,
        ))
    result.sort(key=lambda session: session.last_record_at, reverse=True)
    return tuple(result)
