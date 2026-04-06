"""
ADK entry — `adk web adk_agents` then pick app `sprint_planner`.

Do not nest `tools/` or `subagents/` folders here: ADK lists every
subdirectory of the agents dir as a separate app and imports it by short
name, which breaks `agents.tools`-style packages.
"""

from dotenv import load_dotenv

load_dotenv()

from sprint_planner.logging_config import configure_logging
from sprint_planner.master_agent import master_agent

configure_logging()
root_agent = master_agent
