"""
Quick smoke-test for the Sprint Planner agents.

Usage (from project root):
    PYTHONPATH=.:adk_agents python scripts/test_agent.py

Sends the sample sprint brief through the ADK runner and prints the result.
No browser, no server — direct in-process call.
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ADK discovers agents inside adk_agents/ by folder name.
# For direct import we replicate that: add adk_agents/ to the path so that
# `sprint_planner` is importable as a top-level package (same as adk web does).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)                         # project root → finds sprint_mcp
sys.path.insert(0, os.path.join(_ROOT, "adk_agents"))  # adk_agents → finds sprint_planner

SAMPLE_INPUT = (
    "Sprint starts Monday, we need to finish auth module, "
    "fix 3 bugs, write tests, and do a demo Friday"
)


async def run() -> None:
    from google.adk.runners import InMemoryRunner  # noqa: PLC0415
    from sprint_planner.agent import root_agent    # noqa: PLC0415

    runner = InMemoryRunner(agent=root_agent, app_name="sprint_planner_test")
    session = await runner.session_service.create_session(
        app_name="sprint_planner_test",
        user_id="test_user",
    )

    from google.genai.types import Content, Part  # noqa: PLC0415

    user_message = Content(role="user", parts=[Part(text=SAMPLE_INPUT)])

    print("=" * 60)
    print("INPUT:", SAMPLE_INPUT)
    print("=" * 60)

    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response():
            for part in (event.content.parts or []):
                if part.text:
                    print("\nFINAL RESPONSE:\n")
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(run())
