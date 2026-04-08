import os
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

def get_azure_devops_toolset() -> MCPToolset:
    return MCPToolset(
        connection_params=StdioServerParameters(
            command="python",
            args=["mcp_servers/azure_devops_server.py"],
            env={
                "AZURE_DEVOPS_ORG_URL": os.getenv("AZURE_DEVOPS_ORG_URL"),
                "AZURE_DEVOPS_PAT":     os.getenv("AZURE_DEVOPS_PAT"),
                "AZURE_DEVOPS_PROJECT": os.getenv("AZURE_DEVOPS_PROJECT"),
            }
        )
    )
