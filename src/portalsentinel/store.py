from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from portalsentinel.models import ActionPlan, EventRecord, SessionRecord, utc_now_iso


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def create_session(self, *, mode: str, intent: str, status: str, plan: ActionPlan | None = None) -> str:
        session_id = str(uuid4())
        now = utc_now_iso()
        plan_json = plan.model_dump_json() if plan else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions(session_id, mode, intent, status, plan_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, mode, intent, status, plan_json, now, now),
            )
            self._conn.commit()
        return session_id

    def update_session(self, session_id: str, *, status: str | None = None, plan: ActionPlan | None = None) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id, status, plan_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return
            next_status = status if status is not None else row["status"]
            next_plan = plan.model_dump_json() if plan is not None else row["plan_json"]
            now = utc_now_iso()
            self._conn.execute(
                """
                UPDATE sessions
                SET status = ?, plan_json = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (next_status, next_plan, now, session_id),
            )
            self._conn.commit()

    def log_event(self, *, source: str, event_type: str, payload: dict[str, Any], session_id: str | None = None) -> int:
        now = utc_now_iso()
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO events(session_id, source, event_type, payload_json, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (session_id, source, event_type, json.dumps(payload), now),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def list_events(self, *, session_id: str | None = None, limit: int = 200) -> list[EventRecord]:
        query = """
            SELECT event_id, session_id, source, event_type, payload_json, created_at
            FROM events
        """
        params: tuple[Any, ...]
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id, limit)
            query += " ORDER BY event_id DESC LIMIT ?"
        else:
            params = (limit,)
            query += " ORDER BY event_id DESC LIMIT ?"

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        events: list[EventRecord] = []
        for row in rows:
            events.append(
                EventRecord(
                    event_id=row["event_id"],
                    session_id=row["session_id"],
                    source=row["source"],
                    event_type=row["event_type"],
                    payload=json.loads(row["payload_json"]),
                    created_at=row["created_at"],
                )
            )
        return events

    def list_sessions(self, limit: int = 100) -> list[SessionRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT session_id, mode, intent, status, plan_json, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        sessions: list[SessionRecord] = []
        for row in rows:
            parsed_plan = ActionPlan.model_validate_json(row["plan_json"]) if row["plan_json"] else None
            sessions.append(
                SessionRecord(
                    session_id=row["session_id"],
                    mode=row["mode"],
                    intent=row["intent"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    plan=parsed_plan,
                )
            )
        return sessions

