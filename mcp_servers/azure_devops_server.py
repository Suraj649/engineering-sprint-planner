import os
import asyncio
import json
import base64
import aiohttp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

ORG_URL     = os.getenv("AZURE_DEVOPS_ORG_URL")
PAT         = os.getenv("AZURE_DEVOPS_PAT")
PROJECT     = os.getenv("AZURE_DEVOPS_PROJECT")
API_VERSION = "7.1"

server = Server("azure-devops")

def get_headers() -> dict:
    token = base64.b64encode(f":{PAT}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

async def az_get(path: str) -> dict:
    url = f"{ORG_URL}/{PROJECT}/_apis/{path}?api-version={API_VERSION}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as r:
            return await r.json()

async def az_post(path: str, body: dict) -> dict:
    url = f"{ORG_URL}/{PROJECT}/_apis/{path}?api-version={API_VERSION}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=body) as r:
            return await r.json()

async def az_patch(path: str, body: list) -> dict:
    url = f"{ORG_URL}/{PROJECT}/_apis/{path}?api-version={API_VERSION}"
    headers = {**get_headers(), "Content-Type": "application/json-patch+json"}
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=body) as r:
            return await r.json()

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_current_sprint",
            description="Get current active sprint details",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_sprint_work_items",
            description="Get all work items in current or specified sprint",
            inputSchema={
                "type": "object",
                "properties": {
                    "iteration_path": {
                        "type": "string",
                        "description": "Sprint path e.g. 'MyProject\\Sprint 1'"
                    }
                }
            }
        ),
        Tool(
            name="create_work_item",
            description="Create a Task, Bug, or User Story on the agile board",
            inputSchema={
                "type": "object",
                "required": ["title", "type"],
                "properties": {
                    "title":          {"type": "string"},
                    "type":           {"type": "string", "enum": ["Task", "Bug", "User Story", "Epic"]},
                    "description":    {"type": "string"},
                    "assigned_to":    {"type": "string"},
                    "iteration_path": {"type": "string"},
                    "story_points":   {"type": "number"},
                }
            }
        ),
        Tool(
            name="update_work_item",
            description="Update state or fields of a work item",
            inputSchema={
                "type": "object",
                "required": ["work_item_id"],
                "properties": {
                    "work_item_id": {"type": "integer"},
                    "state":        {"type": "string", "enum": ["New", "Active", "Resolved", "Closed"]},
                    "assigned_to":  {"type": "string"},
                    "title":        {"type": "string"},
                }
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "get_current_sprint":
        data   = await az_get("work/teamsettings/iterations?$timeframe=current")
        sprint = data.get("value", [{}])[0]
        result = {
            "name":       sprint.get("name"),
            "start_date": sprint.get("attributes", {}).get("startDate"),
            "end_date":   sprint.get("attributes", {}).get("finishDate"),
            "path":       sprint.get("path"),
        }

    elif name == "get_sprint_work_items":
        iteration = arguments.get("iteration_path", "@CurrentIteration")
        wiql = {
            "query": f"""
                SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo]
                FROM   WorkItems
                WHERE  [System.IterationPath] = '{iteration}'
                AND    [System.TeamProject] = '{PROJECT}'
            """
        }
        data = await az_post("wit/wiql", wiql)
        ids  = [str(i["id"]) for i in data.get("workItems", [])]
        if not ids:
            result = {"work_items": []}
        else:
            details = await az_get(f"wit/workitems?ids={','.join(ids)}&fields=System.Id,System.Title,System.State,System.AssignedTo")
            result  = {"work_items": details.get("value", [])}

    elif name == "create_work_item":
        item_type = arguments["type"].replace(" ", "%20")
        patch = [
            {"op": "add", "path": "/fields/System.Title",       "value": arguments["title"]},
            {"op": "add", "path": "/fields/System.Description", "value": arguments.get("description", "")},
        ]
        if arguments.get("assigned_to"):
            patch.append({"op": "add", "path": "/fields/System.AssignedTo",   "value": arguments["assigned_to"]})
        if arguments.get("iteration_path"):
            patch.append({"op": "add", "path": "/fields/System.IterationPath","value": arguments["iteration_path"]})
        if arguments.get("story_points"):
            patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints", "value": arguments["story_points"]})
        result = await az_patch(f"wit/workitems/${item_type}", patch)

    elif name == "update_work_item":
        work_item_id = arguments.pop("work_item_id")
        field_map = {
            "state":       "System.State",
            "assigned_to": "System.AssignedTo",
            "title":       "System.Title",
        }
        patch = [
            {"op": "replace", "path": f"/fields/{field}", "value": arguments[key]}
            for key, field in field_map.items() if key in arguments
        ]
        result = await az_patch(f"wit/workitems/{work_item_id}", patch)

    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
