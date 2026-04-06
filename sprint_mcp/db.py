"""
Persistence layer.

1) **AlloyDB** (omnexis-repo style): set `GOOGLE_CLOUD_*` + `ALLOYDB_*` env vars.
   Uses `google.cloud.alloydb.connector.AsyncConnector` + asyncpg.

2) **Generic Postgres URL**: set `DATABASE_URL` (e.g. Cloud SQL via proxy).
   Uses SQLAlchemy + pg8000.

If neither is configured, agents fall back to in-memory notes (no sprint table).

Public API (used by sprint_api/main.py and mcp_stubs):
  is_configured(), database_backend()
  init_db_startup(), shutdown_db()
  insert_sprint()
  write_note_db(), get_notes_db(), list_sprint_ids()
  save_plan_session(), get_plan_session()
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def run_async(coro):
    """Run async AlloyDB code from sync ADK tools (avoids nested event loops)."""

    def _runner() -> Any:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


class Base(DeclarativeBase):
    pass


class SprintRow(Base):
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sprint_name: Mapped[str] = mapped_column(String(512))
    team: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class SprintNoteRow(Base):
    __tablename__ = "sprint_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sprint_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class PlanSessionRow(Base):
    __tablename__ = "plan_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_input: Mapped[str] = mapped_column(Text())
    sprint_id: Mapped[str] = mapped_column(String(128))
    sprint_name: Mapped[str] = mapped_column(String(512))
    team: Mapped[str] = mapped_column(String(256))
    summary_text: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class PlanTaskRow(Base):
    __tablename__ = "plan_tasks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(Text())
    description: Mapped[str] = mapped_column(Text(), default="")
    issue_type: Mapped[str] = mapped_column(String(64), default="feature")
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    story_points: Mapped[int] = mapped_column(Integer(), default=3)
    estimated_hours: Mapped[float] = mapped_column(Float(), default=4.0)
    due: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class PlanEventRow(Base):
    __tablename__ = "plan_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    task_id: Mapped[str] = mapped_column(String(128), default="")
    task_title: Mapped[str] = mapped_column(Text())
    start_time: Mapped[str] = mapped_column(String(64))
    end_time: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text(), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


def database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def _alloydb_ready() -> bool:
    from sprint_mcp.alloydb_async import alloydb_configured

    return alloydb_configured()


def is_configured() -> bool:
    return bool(database_url()) or _alloydb_ready()


def database_backend() -> Literal["off", "postgres", "alloydb"]:
    if _alloydb_ready():
        return "alloydb"
    if database_url():
        return "postgres"
    return "off"


def _get_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    url = database_url()
    if not url:
        return None
    _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def _init_sqlalchemy_tables() -> bool:
    eng = _get_engine()
    if eng is None:
        return False
    Base.metadata.create_all(eng)
    logger.info("SQLAlchemy tables ensured (sprints, sprint_notes)")
    return True


async def init_db_startup() -> bool:
    """FastAPI lifespan: AlloyDB async init or SQLAlchemy in thread."""
    from sprint_mcp import alloydb_async as adb

    if _alloydb_ready():
        await adb.init_db()
        return True
    if database_url():
        await asyncio.to_thread(_init_sqlalchemy_tables)
        return True
    logger.info("No DATABASE_URL or AlloyDB env — DB persistence off")
    return False


async def shutdown_db() -> None:
    from sprint_mcp import alloydb_async as adb

    global _engine, _SessionLocal
    if _alloydb_ready():
        await adb.close_pool()
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("SQLAlchemy engine disposed")


def init_db() -> bool:
    """Sync entry (legacy): prefer init_db_startup from async lifespan."""
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        run_async(adb.init_db())
        return True
    eng = _get_engine()
    if eng is None:
        logger.info("DATABASE_URL not set — skipping DB init (in-memory fallbacks)")
        return False
    Base.metadata.create_all(eng)
    logger.info("DB tables ensured (sprints, sprint_notes)")
    return True


def insert_sprint(sprint_id: str, sprint_name: str, team: str) -> None:
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        run_async(adb.insert_sprint(sprint_id, sprint_name, team))
        return

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        return
    with _SessionLocal() as session:
        row = session.get(SprintRow, sprint_id)
        if row is None:
            session.add(SprintRow(id=sprint_id, sprint_name=sprint_name, team=team))
            session.commit()
            logger.info("insert_sprint | id=%s", sprint_id)
        else:
            row.sprint_name = sprint_name
            row.team = team
            session.commit()
            logger.info("update_sprint | id=%s", sprint_id)


def write_note_db(sprint_id: str, content: str) -> dict[str, Any]:
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        return run_async(adb.write_note(sprint_id, content))

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")

    with _SessionLocal() as session:
        session.add(SprintNoteRow(sprint_id=sprint_id, content=content))
        session.commit()
        count = session.scalar(
            select(func.count()).select_from(SprintNoteRow).where(SprintNoteRow.sprint_id == sprint_id)
        )
        count = int(count or 0)
    return {"status": "saved", "sprint_id": sprint_id, "notes_count": count}


def list_sprint_ids() -> list[str]:
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        return run_async(adb.list_sprint_ids())

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        return []
    with _SessionLocal() as session:
        from_sprints = session.scalars(select(SprintRow.id)).all()
        from_notes = session.scalars(select(SprintNoteRow.sprint_id).distinct()).all()
    return sorted(set(from_sprints) | set(from_notes))


def get_notes_db(sprint_id: str) -> list[dict[str, Any]]:
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        return run_async(adb.get_notes(sprint_id))

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")

    with _SessionLocal() as session:
        rows = list(
            session.scalars(
                select(SprintNoteRow)
                .where(SprintNoteRow.sprint_id == sprint_id)
                .order_by(SprintNoteRow.created_at.asc())
            ).all()
        )
    return [
        {
            "sprint_id": r.sprint_id,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
        }
        for r in rows
    ]


def save_plan_session(
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
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        run_async(
            adb.save_plan_session(
                session_id, user_input, sprint_id, sprint_name,
                team, summary_text, tasks, events,
            )
        )
        return

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        logger.warning("save_plan_session: no DB configured — skipping persistence")
        return

    with _SessionLocal() as db_session:
        db_session.add(PlanSessionRow(
            id=session_id,
            user_input=user_input,
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            team=team,
            summary_text=summary_text,
        ))
        for task in tasks:
            db_session.add(PlanTaskRow(
                id=task.get("id", str(uuid.uuid4())),
                session_id=session_id,
                title=task.get("title", ""),
                description=task.get("description", ""),
                issue_type=task.get("issue_type", "feature"),
                priority=task.get("priority", "medium"),
                story_points=int(task.get("story_points", 3)),
                estimated_hours=float(task.get("estimated_hours", 4.0)),
                due=task.get("due"),
            ))
        for event in events:
            db_session.add(PlanEventRow(
                id=event.get("id", str(uuid.uuid4())),
                session_id=session_id,
                task_id=event.get("task_id", ""),
                task_title=event.get("task_title", ""),
                start_time=event.get("start", ""),
                end_time=event.get("end", ""),
                notes=event.get("notes", ""),
            ))
        db_session.commit()
    logger.info("save_plan_session | session=%s tasks=%d events=%d", session_id, len(tasks), len(events))


def get_plan_session(session_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a saved plan — mirrors omnexis-repo get_session."""
    if _alloydb_ready():
        from sprint_mcp import alloydb_async as adb

        return run_async(adb.get_plan_session(session_id))

    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        return None

    with _SessionLocal() as db_session:
        row = db_session.get(PlanSessionRow, session_id)
        if row is None:
            return None
        tasks = list(
            db_session.scalars(
                select(PlanTaskRow)
                .where(PlanTaskRow.session_id == session_id)
                .order_by(PlanTaskRow.created_at.asc())
            ).all()
        )
        events = list(
            db_session.scalars(
                select(PlanEventRow)
                .where(PlanEventRow.session_id == session_id)
                .order_by(PlanEventRow.created_at.asc())
            ).all()
        )

    return {
        "session_id": session_id,
        "input": row.user_input,
        "sprint_id": row.sprint_id,
        "sprint_name": row.sprint_name,
        "team": row.team,
        "summary": row.summary_text,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "issue_type": t.issue_type,
                "priority": t.priority,
                "story_points": t.story_points,
                "estimated_hours": t.estimated_hours,
                "due": t.due,
            }
            for t in tasks
        ],
        "events": [
            {
                "id": e.id,
                "task_id": e.task_id,
                "task_title": e.task_title,
                "start": e.start_time,
                "end": e.end_time,
                "notes": e.notes,
            }
            for e in events
        ],
    }

