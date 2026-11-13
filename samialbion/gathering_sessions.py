"""Local gathering-session accounting for Sami Albion Manager.

No game traffic capture, client inspection, automation or privileged access.
Events are supplied explicitly by a future *approved* adapter, a manual import,
or tests. This module uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


def _utc(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class GatheredResource:
    item_id: str
    standard: int
    gathering_bonus: int
    premium_bonus: int

    @property
    def total(self) -> int:
        return self.standard + self.gathering_bonus + self.premium_bonus


@dataclass(frozen=True)
class GatheringSummary:
    session_id: str
    character: str
    started_at: str
    ended_at: str | None
    duration_seconds: float
    event_count: int
    resources: tuple[GatheredResource, ...]
    known_silver_value: int
    unpriced_resource_ids: tuple[str, ...]

    @property
    def total_resources(self) -> int:
        return sum(resource.total for resource in self.resources)

    @property
    def resources_per_hour(self) -> float:
        return self.total_resources * 3600 / self.duration_seconds if self.duration_seconds > 0 else 0.0

    @property
    def estimated_silver_per_hour(self) -> float | None:
        if self.unpriced_resource_ids:
            return None
        return self.known_silver_value * 3600 / self.duration_seconds if self.duration_seconds > 0 else 0.0


class GatheringStore:
    """Persist gathering sessions separately from the existing crafting calculator.

    Call from the application/UI thread, or arrange a single owner thread. SQLite
    connections are intentionally not shared between worker threads.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.database_path)
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS gathering_sessions (
                session_id TEXT PRIMARY KEY,
                character TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT
            );
            CREATE TABLE IF NOT EXISTS gathering_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES gathering_sessions(session_id),
                occurred_at TEXT NOT NULL,
                item_id TEXT NOT NULL,
                standard INTEGER NOT NULL CHECK (standard >= 0),
                gathering_bonus INTEGER NOT NULL CHECK (gathering_bonus >= 0),
                premium_bonus INTEGER NOT NULL CHECK (premium_bonus >= 0),
                CHECK (standard + gathering_bonus + premium_bonus > 0)
            );
            CREATE INDEX IF NOT EXISTS idx_gathering_session
                ON gathering_events(session_id, item_id);
        """)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "GatheringStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start_session(self, character: str, *, at: datetime | None = None) -> str:
        character = character.strip()
        if not character:
            raise ValueError("Character name cannot be empty")
        if len(character) > 100:
            raise ValueError("Character name is too long")
        session_id = uuid4().hex
        with self._db:
            self._db.execute(
                "INSERT INTO gathering_sessions VALUES (?, ?, ?, NULL)",
                (session_id, character, _utc(at)),
            )
        return session_id

    def end_session(self, session_id: str, *, at: datetime | None = None) -> None:
        row = self._session(session_id)
        if row[3] is not None:
            raise ValueError("Session has already ended")
        ended = _utc(at)
        if datetime.fromisoformat(ended) < datetime.fromisoformat(row[2]):
            raise ValueError("Session cannot end before it starts")
        with self._db:
            self._db.execute(
                "UPDATE gathering_sessions SET ended_at=? WHERE session_id=?",
                (ended, session_id),
            )

    def add_event(
        self, session_id: str, item_id: str, standard: int, *,
        gathering_bonus: int = 0, premium_bonus: int = 0,
        occurred_at: datetime | None = None, event_id: str | None = None,
    ) -> bool:
        """Record one explicitly supplied event; return False for a duplicate id.

        A source must supply a stable event_id to obtain deduplication across
        restarts. Values are not fetched from the game by this module.
        """
        session = self._session(session_id)
        if session[3] is not None:
            raise ValueError("Cannot add an event to a finished session")
        item_id = item_id.strip()
        if not item_id or len(item_id) > 150:
            raise ValueError("Invalid item id")
        amounts = (standard, gathering_bonus, premium_bonus)
        if any(type(value) is not int or value < 0 for value in amounts) or not sum(amounts):
            raise ValueError("Gathering amounts must be nonnegative integers with a positive total")
        occurred = _utc(occurred_at)
        if datetime.fromisoformat(occurred) < datetime.fromisoformat(session[2]):
            raise ValueError("Gathering event precedes session start")
        event_id = event_id or uuid4().hex
        previous = self._db.execute(
            "SELECT session_id, item_id, standard, gathering_bonus, premium_bonus FROM gathering_events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        payload = (session_id, item_id, *amounts)
        if previous is not None:
            if previous != payload:
                raise ValueError("Event id collision with different data")
            return False
        with self._db:
            self._db.execute(
                "INSERT INTO gathering_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, session_id, occurred, item_id, *amounts),
            )
        return True

    def summary(
        self, session_id: str, *, unit_prices: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> GatheringSummary:
        session = self._session(session_id)
        prices = unit_prices or {}
        if any(type(v) is not int or v < 0 for v in prices.values()):
            raise ValueError("Unit prices must be nonnegative integers")
        rows = self._db.execute("""
            SELECT item_id, SUM(standard), SUM(gathering_bonus), SUM(premium_bonus)
            FROM gathering_events WHERE session_id=? GROUP BY item_id ORDER BY item_id
        """, (session_id,)).fetchall()
        resources = tuple(GatheredResource(*row) for row in rows)
        missing = tuple(resource.item_id for resource in resources if resource.item_id not in prices)
        known_silver = sum(resource.total * prices[resource.item_id]
                           for resource in resources if resource.item_id in prices)
        end_time = session[3] or _utc(now)
        elapsed = (datetime.fromisoformat(end_time) - datetime.fromisoformat(session[2])).total_seconds()
        count = self._db.execute(
            "SELECT COUNT(*) FROM gathering_events WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        return GatheringSummary(session[0], session[1], session[2], session[3],
                                max(0.0, elapsed), count, resources, known_silver, missing)

    def list_sessions(self, *, character: str | None = None) -> list[tuple[str, str, str, str | None]]:
        if character is None:
            return self._db.execute(
                "SELECT * FROM gathering_sessions ORDER BY started_at DESC"
            ).fetchall()
        return self._db.execute(
            "SELECT * FROM gathering_sessions WHERE character=? ORDER BY started_at DESC",
            (character,),
        ).fetchall()

    def _session(self, session_id: str) -> tuple[str, str, str, str | None]:
        row = self._db.execute(
            "SELECT * FROM gathering_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown gathering session: {session_id}")
        return row
