"""Story breakdown sub-agent (omnexis task_agent pattern)."""

from __future__ import annotations

import logging
import os

from google.adk import Agent

from sprint_planner.state_tools import store_sprint_stories

logger = logging.getLogger(__name__)

_MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")

story_breakdown_agent = Agent(
    name="story_breakdown_agent",
    model=_MODEL,
    description=(
        "Parses a sprint brain-dump into discrete engineering stories "
        "(features, bugs, chores, tests, demo prep)."
    ),
    instruction="""
You are the Story Breakdown specialist for an engineering team.

Your sole responsibility: read the sprint brief from the conversation and
from session state (SPRINT_NAME, TEAM, RAW_MESSAGE are set by the master)
and break it into **6 to 10** engineering stories (not necessarily exactly 5).

For each story provide:
  - id             : "story_1", "story_2", ... in order
  - title          : concise, action-oriented (verb + object)
  - description    : one sentence — acceptance-oriented when possible
  - issue_type     : "feature" | "bug" | "chore" | "test" | "spike" | "demo" | "other"
  - priority       : "high" | "medium" | "low"

Rules:
  - Include explicit items the user mentioned (e.g. "auth module", "3 bugs",
    "tests", "demo Friday") as separate or grouped stories as appropriate.
  - Do NOT assign story points or hours here — only titles, types, priority.

Steps:
1. Compose a JSON **array** of story objects (6–10 items).

2. Call `store_sprint_stories` with that JSON string as `stories_json`.

3. After the tool succeeds, respond with ONLY this single line:
   "Story breakdown complete — stories saved."
""",
    tools=[store_sprint_stories],
)

logger.debug("story_breakdown_agent | model=%s", _MODEL)
