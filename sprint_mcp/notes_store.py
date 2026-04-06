"""
In-memory sprint notes store.

Stores notes per sprint_id as a list of timestamped entries.
Swap the backing store for a real DB in Phase 2 without changing the interface.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# sprint_id -> list of note dicts
_store: dict[str, list[dict[str, Any]]] = {}


def write_note(sprint_id: str, content: str) -> dict[str, Any]:
    """Append a note entry for the given sprint."""
    entry = {
        "sprint_id": sprint_id,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _store.setdefault(sprint_id, []).append(entry)
    logger.info("write_note | sprint=%s notes_count=%d", sprint_id, len(_store[sprint_id]))
    return {"status": "saved", "sprint_id": sprint_id, "notes_count": len(_store[sprint_id])}


def get_notes(sprint_id: str) -> list[dict[str, Any]]:
    """Return all notes for a sprint (empty list if none)."""
    notes = _store.get(sprint_id, [])
    logger.info("get_notes | sprint=%s count=%d", sprint_id, len(notes))
    return notes


def list_sprints() -> list[str]:
    """Return all sprint IDs that have notes."""
    return list(_store.keys())
