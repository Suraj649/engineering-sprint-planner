"""
Postgres persistence (Cloud SQL / AlloyDB / any PostgreSQL).

Set DATABASE_URL, e.g.:
  postgresql+pg8000://USER:PASS@HOST:5432/DBNAME

Tables are created on API startup via init_db().
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


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


def database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def is_configured() -> bool:
    return database_url() is not None


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


def init_db() -> bool:
    """Create tables if DATABASE_URL is set. Returns True if DB is ready."""
    eng = _get_engine()
    if eng is None:
        logger.info("DATABASE_URL not set — skipping DB init (in-memory fallbacks)")
        return False
    Base.metadata.create_all(eng)
    logger.info("DB tables ensured (sprints, sprint_notes)")
    return True


def insert_sprint(sprint_id: str, sprint_name: str, team: str) -> None:
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
    eng = _get_engine()
    if eng is None or _SessionLocal is None:
        return []
    with _SessionLocal() as session:
        from_sprints = session.scalars(select(SprintRow.id)).all()
        from_notes = session.scalars(select(SprintNoteRow.sprint_id).distinct()).all()
    return sorted(set(from_sprints) | set(from_notes))


def get_notes_db(sprint_id: str) -> list[dict[str, Any]]:
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
