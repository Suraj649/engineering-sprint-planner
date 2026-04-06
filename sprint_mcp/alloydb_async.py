"""
AlloyDB connectivity — same pattern as omnexis-repo/backend/db.py.

Uses google.cloud.alloydb.connector.AsyncConnector + asyncpg.

Required env (see .env.example):
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
  ALLOYDB_CLUSTER, ALLOYDB_INSTANCE
  ALLOYDB_USER, ALLOYDB_PASSWORD, ALLOYDB_DATABASE
"""

from __future__ import annotations

import asyncio
import logging
import os
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
"""


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
    logger.info("AlloyDB tables ensured (sprints, sprint_notes)")


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
