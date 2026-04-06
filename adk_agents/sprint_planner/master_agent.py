"""Master orchestrator — Engineering Sprint Planner."""

from __future__ import annotations

import logging
import os

from google.adk import Agent
from google.adk.agents import SequentialAgent

from sprint_planner.estimation_agent import estimation_agent
from sprint_planner.mcp_stubs import (
    db_create_sprint,
    mcp_block_calendar,
    mcp_push_github,
    mcp_push_tracker,
    mcp_write_note,
)
from sprint_planner.notes_agent import notes_agent
from sprint_planner.sprint_calendar_agent import sprint_calendar_agent
from sprint_planner.state_tools import (
    retrieve_schedule,
    retrieve_scaffolded_tasks,
    retrieve_sprint_notes,
    store_sprint_context,
)
from sprint_planner.story_breakdown_agent import story_breakdown_agent

logger = logging.getLogger(__name__)

_MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")

sprint_pipeline = SequentialAgent(
    name="sprint_pipeline",
    description=(
        "Runs story_breakdown_agent → estimation_agent → sprint_calendar_agent → notes_agent. "
        "Intermediate data lives in session state."
    ),
    sub_agents=[story_breakdown_agent, estimation_agent, sprint_calendar_agent, notes_agent],
)

master_agent = Agent(
    name="master_agent",
    model=_MODEL,
    description=(
        "Orchestrates sprint planning: stories, estimates, calendar, notes, "
        "and pushes to tracker, GitHub, and Calendar."
    ),
    instruction="""
You are the Primary Agent for the Engineering Sprint Planner.

GOAL: Given a sprint brain-dump, run the full workflow and return a concise
plain-text summary for the engineer or scrum master.

────────────────────────────────────────────────
WORKFLOW (execute every step IN ORDER, no skips)
────────────────────────────────────────────────

STEP 1 — Identify the sprint (infer — never ask the user).
  From the user's message extract:
    • sprint_name : short label (e.g. "Sprint 12 — Auth & stability")
    • team        : product or team name; if missing use "Engineering"
  → Call `store_sprint_context(sprint_name, team, raw_message)` using the
    user's exact message as raw_message.

STEP 2 — Create sprint record in DB (stub).
  → Call `db_create_sprint(sprint_name, team)`

STEP 3 — Run the sequential pipeline.
  → Transfer to `sprint_pipeline`
    story_breakdown_agent → estimation_agent → sprint_calendar_agent → notes_agent
    State keys populated: SPRINT_STORIES, SCAFFOLDED_TASKS, SCHEDULE, SPRINT_NOTES

STEP 4 — Push stories to Azure DevOps tracker.
  → Call `retrieve_scaffolded_tasks`, then call `mcp_push_tracker` with the
    exact `tasks_json` string from the tool result.

STEP 5 — Mirror issues on GitHub (stub).
  → Call `mcp_push_github` with the **same** `tasks_json` string from Step 4.

STEP 6 — Book Google Calendar slots (stub until credentials configured).
  → Call `retrieve_schedule`, then call `mcp_block_calendar` with the exact
    `schedule_json` string from the tool result.

STEP 7 — Respond in friendly plain text.
  Cover:
    ✓ Sprint name and team
    ✓ Bullet or numbered list of stories (title, points, hours)
    ✓ Calendar: how many slots and approximate date range
    ✓ Notes: goals, risks, decisions captured
    ✓ What completed: DB sprint, tracker, GitHub, Calendar, notes (audit)

  FORMAT:
    • Plain text only — no raw JSON, no markdown code fences.
    • Exception: if the user explicitly asks for JSON, output ONLY one JSON
      object matching this shape (no text outside it):
      {
        "version": "1.0",
        "status": "complete",
        "sprint_name": "<name>",
        "team": "<team>",
        "summary": "<one sentence>",
        "stories": [
          {
            "id": "story_1",
            "title": "<t>",
            "description": "<d>",
            "issue_type": "feature|bug|chore|test|spike|demo|other",
            "priority": "high|medium|low",
            "story_points": 3,
            "estimated_hours": 4.0,
            "due": "<milestone>"
          }
        ],
        "events": [
          {
            "task_id": "<id>",
            "task_title": "<t>",
            "start": "YYYY-MM-DDTHH:MM:00",
            "end": "YYYY-MM-DDTHH:MM:00",
            "notes": ""
          }
        ],
        "mcp_actions": ["db_create_sprint(..)", "mcp_push_tracker(..)", ...]
      }
      Populate mcp_actions from session state: include db_create_sprint,
      mcp_push_tracker, mcp_push_github, mcp_block_calendar, mcp_write_note.

────────────────────────────────────────────────
GLOBAL RULES
────────────────────────────────────────────────
• Never ask clarifying questions — infer and proceed.
• Complete all steps before the final answer.
• Greetings or "what can you do?" → answer briefly and skip the workflow.
""",
    tools=[
        store_sprint_context,
        db_create_sprint,
        retrieve_scaffolded_tasks,
        retrieve_schedule,
        retrieve_sprint_notes,
        mcp_push_tracker,
        mcp_push_github,
        mcp_block_calendar,
        mcp_write_note,
    ],
    sub_agents=[sprint_pipeline],
)

logger.debug(
    "master_agent ready | pipeline=%s",
    [a.name for a in sprint_pipeline.sub_agents],
)
