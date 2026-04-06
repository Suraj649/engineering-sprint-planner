"""
Azure DevOps Boards client.

Creates work items via the Azure DevOps REST API.

Required env vars:
  AZURE_DEVOPS_ORG            — organisation slug (from dev.azure.com/{org})
  AZURE_DEVOPS_PROJECT        — project name
  AZURE_DEVOPS_PAT            — Personal Access Token (Work Items: Read & write)
  AZURE_DEVOPS_WORK_ITEM_TYPE — type matching your process template
                                Common values: "Issue" (Basic), "User Story" (Agile),
                                "Product Backlog Item" (Scrum). Default: "Issue"
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_AZDO_BASE = "https://dev.azure.com/{org}/{project}/_apis"
_API_VER = "api-version=7.1"


def _auth_header() -> dict[str, str]:
    pat = os.environ["AZURE_DEVOPS_PAT"]
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _create_work_item(title: str, description: str, item_type: str) -> dict[str, Any]:
    org = os.environ["AZURE_DEVOPS_ORG"]
    project = os.environ["AZURE_DEVOPS_PROJECT"]
    encoded_type = requests.utils.quote(item_type)
    url = f"{_AZDO_BASE.format(org=org, project=project)}/wit/workitems/${encoded_type}?{_API_VER}"

    body = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": description},
    ]

    resp = requests.post(
        url,
        headers={**_auth_header(), "Content-Type": "application/json-patch+json"},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def push_stories(stories_json: str) -> dict[str, Any]:
    """
    Create one Azure DevOps work item per story in stories_json.

    Falls back to stub mode when AZURE_DEVOPS_PAT is not set.
    Returns a result dict with status, issues_created, work_item_ids, errors.
    """
    if not os.environ.get("AZURE_DEVOPS_PAT"):
        try:
            count = len(json.loads(stories_json)) if stories_json else 0
        except (json.JSONDecodeError, TypeError):
            count = 0
        logger.warning("AZURE_DEVOPS_PAT not set — stub mode")
        return {"status": "stub", "issues_created": count, "tracker": "azure_devops"}

    try:
        stories: list[dict[str, Any]] = json.loads(stories_json)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "message": "Invalid JSON in stories_json"}

    item_type = os.environ.get("AZURE_DEVOPS_WORK_ITEM_TYPE", "Issue")
    created_ids: list[int] = []
    errors: list[str] = []

    for story in stories:
        title = story.get("title", "Untitled story")
        description = (
            f"{story.get('description', '')}<br/>"
            f"<b>Type:</b> {story.get('issue_type', '')} | "
            f"<b>Priority:</b> {story.get('priority', '')} | "
            f"<b>Points:</b> {story.get('story_points', '')} | "
            f"<b>Est. hours:</b> {story.get('estimated_hours', '')}"
        )
        try:
            result = _create_work_item(title, description, item_type)
            created_ids.append(result.get("id"))
            logger.info("Created Azure DevOps work item #%s: %s", result.get("id"), title)
        except requests.HTTPError as exc:
            msg = f"HTTPError '{title}': {exc.response.status_code} {exc.response.text}"
            logger.error(msg)
            errors.append(msg)
        except Exception as exc:
            msg = f"Error '{title}': {exc}"
            logger.error(msg)
            errors.append(msg)

    return {
        "status": "partial" if errors else "pushed",
        "issues_created": len(created_ids),
        "work_item_ids": created_ids,
        "errors": errors,
        "tracker": "azure_devops",
    }
