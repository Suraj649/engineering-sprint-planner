"""Estimation sub-agent."""

from __future__ import annotations

import logging
import os

from google.adk import Agent

from sprint_planner.state_tools import retrieve_sprint_stories, store_scaffolded_tasks

logger = logging.getLogger(__name__)

_MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")

estimation_agent = Agent(
    name="estimation_agent",
    model=_MODEL,
    description=(
        "Reads sprint stories and adds Fibonacci story points and estimated hours."
    ),
    instruction="""
You are the Estimation specialist.

Steps:
1. Call `retrieve_sprint_stories` to get `stories_json`.

2. For **each** story in that array, produce one object with ALL fields:
   - id, title, description, issue_type, priority  (preserve from input)
   - story_points   : Fibonacci only — 1, 2, 3, 5, 8, or 13
   - estimated_hours: realistic float (e.g. 2, 4, 8); align loosely with points
   - due            : relative milestone (e.g. "Mon", "Wed", "Fri demo")

3. Call `store_scaffolded_tasks` with the JSON **array** string as `tasks_json`.

4. After the tool succeeds, respond with ONLY this single line:
   "Estimation complete — story points and hours saved."
""",
    tools=[retrieve_sprint_stories, store_scaffolded_tasks],
)

logger.debug("estimation_agent | model=%s", _MODEL)
