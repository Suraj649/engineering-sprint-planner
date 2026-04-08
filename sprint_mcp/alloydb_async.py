"""
AlloyDB connectivity — same pattern as omnexis-repo/backend/db.py.

Uses google.cloud.alloydb.connector.AsyncConnector + asyncpg.

Required env (see .env.example):
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
  ALLOYDB_CLUSTER, ALLOYDB_INSTANCE
  ALLOYDB_USER, ALLOYDB_PASSWORD, ALLOYDB_DATABASE

Tables (mirrors omnexis schema):
  sprints       — sprint identity
  sprint_notes  — per-sprint notes
  plan_sessions — full plan snapshot (input + stories + schedule)
  plan_tasks    — individual stories/tasks keyed to a session
  plan_events   — calendar slots keyed to a session
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

_connector: Any = None
_pool: Any = None


def alloydb_configured() -> bool:
    required = (
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "ALLOYDB_CLUSTER",
        "ALLOYDB_INSTANCE",
        "ALLOYDB_USER",
        "ALLOYDB_PASSWORD",
        "ALLOYDB_DATABASE",
    )
    return all(os.getenv(k, "").strip() for k in required)


def instance_uri() -> str:
    return (
        f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}"
        f"/locations/{os.environ['GOOGLE_CLOUD_LOCATION']}"
        f"/clusters/{os.environ['ALLOYDB_CLUSTER']}"
        f"/instances/{os.environ['ALLOYDB_INSTANCE']}"
    )


async def get_pool() -> Any:
    import asyncpg
    from google.cloud.alloydb.connector import AsyncConnector

    global _pool, _connector
    if _pool is None:
        _connector = AsyncConnector()

        async def _connect(*args: Any, **kwargs: Any) -> Any:
            kwargs.pop("loop", None)
            kwargs.pop("connection_class", None)
            kwargs.pop("record_class", None)
            conn = await asyncio.wait_for(
                _connector.connect(
                    instance_uri(),
                    "asyncpg",
                    user=os.environ["ALLOYDB_USER"],
                    password=os.environ["ALLOYDB_PASSWORD"],
                    db=os.environ["ALLOYDB_DATABASE"],
                ),
                timeout=20,
            )
            return conn

        _pool = await asyncpg.create_pool(min_size=1, max_size=5, connect=_connect)
        logger.info("AlloyDB pool ready (engineering-sprint-planner)")
    return _pool


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sprints (
    id           VARCHAR(128) PRIMARY KEY,
    sprint_name  VARCHAR(512) NOT NULL,
    team         VARCHAR(256) NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sprint_notes (
    id           BIGSERIAL PRIMARY KEY,
    sprint_id    VARCHAR(128) NOT NULL,
    content      TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sprint_notes_sprint_id ON sprint_notes (sprint_id);

CREATE TABLE IF NOT EXISTS plan_sessions (
    id           VARCHAR(128) PRIMARY KEY,
    user_input   TEXT NOT NULL,
    sprint_id    VARCHAR(128),
    sprint_name  VARCHAR(512),
    team         VARCHAR(256),
    summary_text TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plan_tasks (
    id              VARCHAR(128) PRIMARY KEY,
    session_id      VARCHAR(128) REFERENCES plan_sessions(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    issue_type      TEXT DEFAULT 'feature',
    priority        TEXT DEFAULT 'medium',
    story_points    INT DEFAULT 3,
    estimated_hours FLOAT DEFAULT 4.0,
    due             TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plan_events (
    id           VARCHAR(128) PRIMARY KEY,
    session_id   VARCHAR(128) REFERENCES plan_sessions(id) ON DELETE CASCADE,
    task_id      TEXT,
    task_title   TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_tasks_session ON plan_tasks (session_id);
CREATE INDEX IF NOT EXISTS idx_plan_events_session ON plan_events (session_id);
"""


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
    logger.info("AlloyDB tables ensured (sprints, sprint_notes, plan_sessions, plan_tasks, plan_events)")


async def insert_sprint(sprint_id: str, sprint_name: str, team: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sprints (id, sprint_name, team)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE SET
                sprint_name = EXCLUDED.sprint_name,
                team = EXCLUDED.team
            """,
            sprint_id,
            sprint_name,
            team,
        )
    logger.info("AlloyDB insert_sprint | id=%s", sprint_id)


async def save_plan_session(
    session_id: str,
    user_input: str,
    sprint_id: str,
    sprint_name: str,
    team: str,
    summary_text: str,
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    """Persist a full plan result — mirrors omnexis-repo save_session."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO plan_sessions (id, user_input, sprint_id, sprint_name, team, summary_text)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                session_id,
                user_input,
                sprint_id,
                sprint_name,
                team,
                summary_text,
            )

            for task in tasks:
                await conn.execute(
                    """
                    INSERT INTO plan_tasks
                        (id, session_id, title, description, issue_type, priority,
                         story_points, estimated_hours, due)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    task.get("id", str(uuid.uuid4())),
                    session_id,
                    task.get("title", ""),
                    task.get("description", ""),
                    task.get("issue_type", "feature"),
                    task.get("priority", "medium"),
                    int(task.get("story_points", 3)),
                    float(task.get("estimated_hours", 4.0)),
                    task.get("due"),
                )

            for event in events:
                await conn.execute(
                    """
                    INSERT INTO plan_events (id, session_id, task_id, task_title, start_time, end_time, notes)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    event.get("id", str(uuid.uuid4())),
                    session_id,
                    event.get("task_id", ""),
                    event.get("task_title", ""),
                    event.get("start", ""),
                    event.get("end", ""),
                    event.get("notes", ""),
                )

    logger.info(
        "save_plan_session | session=%s tasks=%d events=%d",
        session_id,
        len(tasks),
        len(events),
    )


async def get_plan_session(session_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a full saved plan — mirrors omnexis-repo get_session."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM plan_sessions WHERE id = $1",
            session_id,
        )
        if not row:
            return None
        tasks = await conn.fetch(
            "SELECT * FROM plan_tasks WHERE session_id = $1 ORDER BY created_at",
            session_id,
        )
        events = await conn.fetch(
            "SELECT * FROM plan_events WHERE session_id = $1 ORDER BY created_at",
            session_id,
        )

    return {
        "session_id": session_id,
        "input": row["user_input"],
        "sprint_id": row["sprint_id"],
        "sprint_name": row["sprint_name"],
        "team": row["team"],
        "summary": row["summary_text"],
        "tasks": [
            {
                "id": r["id"],
                "title": r["title"],
                "description": r["description"] or "",
                "issue_type": r["issue_type"],
                "priority": r["priority"],
                "story_points": r["story_points"],
                "estimated_hours": r["estimated_hours"],
                "due": r["due"],
            }
            for r in tasks
        ],
        "events": [
            {
                "id": r["id"],
                "task_id": r["task_id"],
                "task_title": r["task_title"],
                "start": r["start_time"],
                "end": r["end_time"],
                "notes": r["notes"] or "",
            }
            for r in events
        ],
    }


async def write_note(sprint_id: str, content: str) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sprint_notes (sprint_id, content) VALUES ($1, $2)",
            sprint_id,
            content,
        )
        count = await conn.fetchval(
            "SELECT COUNT(*)::bigint FROM sprint_notes WHERE sprint_id = $1",
            sprint_id,
        )
    return {"status": "saved", "sprint_id": sprint_id, "notes_count": int(count or 0)}


async def get_notes(sprint_id: str) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sprint_id, content, created_at
            FROM sprint_notes
            WHERE sprint_id = $1
            ORDER BY created_at ASC
            """,
            sprint_id,
        )
    return [
        {
            "sprint_id": r["sprint_id"],
            "content": r["content"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        }
        for r in rows
    ]


async def list_sprint_ids() -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = {r["id"] for r in await conn.fetch("SELECT id FROM sprints")}
        n = {r["sprint_id"] for r in await conn.fetch("SELECT DISTINCT sprint_id FROM sprint_notes")}
    return sorted(s | n)


async def close_pool() -> None:
    global _pool, _connector
    if _pool:
        await _pool.close()
        _pool = None
    if _connector:
        await _connector.close()
        _connector = None
    logger.info("AlloyDB pool closed")
